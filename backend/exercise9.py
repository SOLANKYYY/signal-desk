"""Validate and display local Exercise 9 evidence; never execute uploaded content."""
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import statistics
import zipfile

MAX_UPLOAD = 1024 * 1024
HOSTS = {f'sd9-mongo{i}:27017' for i in range(1, 4)}
KIT_FILES = ('compose.yaml', 'Dockerfile', 'Dockerfile.submission', '.dockerignore', 'lab9.py', 'start.ps1', 'run-partition.ps1', 'README.md')


def kit_bytes():
    root = Path(__file__).resolve().parents[1] / 'labs' / 'chapter09'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in KIT_FILES:
            archive.write(root / name, 'SignalDesk_Exercise9/' + name)
    return buffer.getvalue()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Measurements must be finite, non-negative numbers.')
    return value


def date(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('A recorded timestamp is required.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None: raise ValueError()
        return parsed
    except ValueError:
        raise ValueError('Use timestamps with a timezone.') from None


def validate(doc):
    try:
        raw = json.dumps(doc, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ValueError('Invalid JSON evidence.') from None
    if len(raw.encode()) > MAX_UPLOAD: raise ValueError('Result exceeds 1 MiB.')
    if doc.get('format') != 'signal-desk-exercise9' or type(doc.get('version')) is not int or doc['version'] != 1:
        raise ValueError('Upload a JSON result produced by the Exercise 9 kit.')
    topology = doc.get('topology')
    if not isinstance(topology, list) or len(topology) != 3 or any(not isinstance(h, str) or h not in HOSTS for h in topology) or set(topology) != HOSTS:
        raise ValueError('Exercise 9 requires the kit’s three data-bearing members.')
    if date(doc.get('finishedAt')) < date(doc.get('startedAt')):
        raise ValueError('Finish time must follow start time.')
    summary = {'activity': doc.get('activity'), 'startedAt': doc['startedAt'], 'finishedAt': doc['finishedAt']}
    if doc.get('activity') == 'latency':
        rows = doc.get('rows')
        if not isinstance(rows, list) or len(rows) != 6:
            raise ValueError('Expected six write concern and journal configurations.')
        seen = set(); computed = []
        for row in rows:
            if not isinstance(row, dict) or type(row.get('w')) not in (int, str) or row.get('w') not in (1, 3, 'majority') or type(row.get('j')) is not bool:
                raise ValueError('Invalid write concern configuration.')
            mode = (row['w'], row['j'])
            if mode in seen: raise ValueError('Duplicate benchmark configuration.')
            seen.add(mode)
            samples = row.get('samplesMs')
            if type(row.get('count')) is not int or row['count'] != 1000 or not isinstance(samples, list) or len(samples) != 1000:
                raise ValueError('Each configuration must contain 1,000 write measurements.')
            values = sorted(number(v) for v in samples)
            elapsed = number(row.get('elapsedMs'))
            if elapsed + 1 < sum(values): raise ValueError('Total time is shorter than its write measurements.')
            computed.append({'w': row['w'], 'j': row['j'], 'count': 1000, 'elapsedMs': elapsed,
                             'averageMs': statistics.mean(values), 'p50Ms': statistics.median(values), 'p99Ms': values[989]})
        summary['rows'] = computed
        summary['majorityJournalDefault'] = doc.get('majorityJournalDefault') if type(doc.get('majorityJournalDefault')) is bool else None
    elif doc.get('activity') == 'partition':
        events = doc.get('events')
        phases = {'baseline', 'one-secondary-offline', 'first-recovery', 'two-secondaries-offline', 'final-recovery'}
        if not isinstance(events, list) or not 5 <= len(events) <= 500:
            raise ValueError('Expected a bounded partition timeline.')
        present = set(); clean = []; recoveries = set(); phase_duration = {}; writes = set()
        previous = None
        for e in events:
            if not isinstance(e, dict) or not isinstance(e.get('phase'), str) or e.get('phase') not in phases or e.get('kind') not in ('status', 'write', 'recovery'):
                raise ValueError('Invalid timeline event.')
            at = date(e.get('at'))
            if previous and at < previous: raise ValueError('Timeline timestamps must be in order.')
            previous = at
            phase = e['phase']; present.add(phase)
            t = number(e.get('elapsedSeconds'))
            phase_duration[phase] = max(t, phase_duration.get(phase, 0))
            item = {k: e[k] for k in ('at', 'phase', 'kind', 'elapsedSeconds')}
            if 'error' in e:
                if not isinstance(e['error'], str) or len(e['error']) > 2000: raise ValueError('Invalid recorded error.')
                item['error'] = e['error']
            if e['kind'] == 'write':
                if type(e.get('w')) not in (int, str) or e.get('w') not in (1, 'majority') or not isinstance(e.get('outcome'), str) or not 1 <= len(e['outcome']) <= 100:
                    raise ValueError('Invalid write probe.')
                item.update(w=e['w'], outcome=e['outcome'], latencyMs=number(e.get('latencyMs')))
                writes.add((phase, e['w']))
            else:
                members = e.get('members', [])
                if not isinstance(members, list) or len(members) > 3: raise ValueError('Invalid member states.')
                names = set()
                for m in members:
                    if not isinstance(m, dict) or not isinstance(m.get('name'), str) or m['name'] not in HOSTS or m['name'] in names or not isinstance(m.get('state'), str) or len(m['state']) > 60 or type(m.get('health')) not in (int, float) or m['health'] not in (0, 1):
                        raise ValueError('Invalid member state.')
                    names.add(m['name'])
                if not members and 'error' not in e: raise ValueError('Status evidence is missing.')
                item['members'] = [{k: m[k] for k in ('name', 'state', 'health')} for m in members]
                if e['kind'] == 'recovery':
                    if e.get('caughtUp') is not True or len(members) != 3 or sorted(m['state'] for m in members) != ['PRIMARY', 'SECONDARY', 'SECONDARY'] or any(m['health'] != 1 for m in members):
                        raise ValueError('Recovery evidence must show three healthy members and catch-up.')
                    item['caughtUp'] = True; recoveries.add(phase)
            clean.append(item)
        if present != phases or not {'first-recovery', 'final-recovery'} <= recoveries or clean[-1]['phase'] != 'final-recovery' or clean[-1]['kind'] != 'recovery':
            raise ValueError('Run both partition phases and verify both recoveries before uploading.')
        for phase in ('one-secondary-offline', 'two-secondaries-offline'):
            if phase_duration.get(phase, 0) < 30 or not {(phase, 1), (phase, 'majority')} <= writes:
                raise ValueError('Each partition needs 30 seconds of observations and both write probes.')
        summary['events'] = clean
        summary['acknowledged'] = sum(e.get('outcome') == 'acknowledged' for e in clean)
        summary['failed'] = sum(e['kind'] == 'write' and e['outcome'] != 'acknowledged' for e in clean)
    else: raise ValueError('Unknown Exercise 9 activity.')
    return raw, summary


def import_run(db, doc):
    raw, summary = validate(doc)
    stored = {'_id': summary['activity'], 'summary': summary, 'rawJson': raw, 'uploadedAt': datetime.now(timezone.utc)}
    db.exercise9_runs.replace_one({'_id': stored['_id']}, stored, upsert=True)
    return {k: v for k, v in stored.items() if k != 'rawJson'}


def list_runs(db):
    return {'runs': list(db.exercise9_runs.find({}, {'rawJson': 0}))}


def get_run(db, key):
    doc = db.exercise9_runs.find_one({'_id': key}) if key in ('latency', 'partition') else None
    if doc:
        doc['document'] = json.loads(doc.pop('rawJson'))
    return doc
