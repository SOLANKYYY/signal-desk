"""Recorded Chapter 8 evidence. Never executes uploaded MongoDB commands."""
import hashlib
import json
from datetime import datetime, timezone

MAX_UPLOAD = 1024 * 1024
ACTIVITIES = {
    'lab_8_1_replica_set.py': ('replication', '8.1 · Replication'),
    'try_8_1_add_arbiter.py': ('arbiter', '8.1 · Add an arbiter'),
    'lab_8_2_failover_monitor.py': ('failover', '8.2 · Failover'),
    'try_8_2_priority_election.py': ('priorities', '8.2 · Election priorities'),
}


def timestamp(value):
    if isinstance(value, dict):
        value = value.get('$date')
    if not isinstance(value, str):
        raise ValueError('Each step needs an ISO executedAt timestamp.')
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Invalid recorded timestamp.') from None
    if not date.tzinfo:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).isoformat()


def validate(document):
    if not isinstance(document, dict) or document.get('script') not in ACTIVITIES:
        raise ValueError('Choose a JSON result from one of the four Chapter 8 scripts.')
    steps = document.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 500:
        raise ValueError('The result must contain 1–500 recorded steps.')
    pending = [(document, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > 32:
            raise ValueError('Result nesting is too deep.')
        if isinstance(value, dict):
            pending.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            pending.extend((v, depth + 1) for v in value)
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get('step'), str) or len(step['step']) > 500 or 'result' not in step:
            raise ValueError('Each recorded step needs a name and a result.')
        timestamp(step.get('executedAt'))
    try:
        raw = json.dumps(document, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ValueError('Invalid JSON result.') from None
    if len(raw.encode('utf-8')) > MAX_UPLOAD:
        raise ValueError('Choose a result smaller than 1 MiB.')
    return raw


def summarize(document):
    """Read the supplied scripts' BSON Extended JSON without evaluating commands."""
    activity_id, title = ACTIVITIES[document['script']]
    timeline, reads, replication, issues = [], [], [], []
    final_members, priorities = {}, {}
    prediction = None
    set_name = None

    def capture(members, at, step):
        nonlocal final_members
        parsed = {}
        if isinstance(members, list):
            for member in members:
                if not isinstance(member, dict):
                    continue
                name = member.get('name')
                state = member.get('stateStr')
                if isinstance(name, str) and isinstance(state, str):
                    parsed[name] = {'name': name, 'state': state, 'health': member.get('health'), 'priority': priorities.get(name)}
        elif isinstance(members, dict):
            for name, member in members.items():
                state = member if isinstance(member, str) else member.get('state') if isinstance(member, dict) else None
                if isinstance(state, str):
                    parsed[name] = {'name': name, 'state': state,
                        'health': member.get('health') if isinstance(member, dict) else None,
                        'priority': member.get('priority', priorities.get(name)) if isinstance(member, dict) else priorities.get(name)}
        if parsed:
            if len(parsed) > 50:
                raise ValueError('Too many replica members in the result.')
            final_members = parsed
            states = {name: m['state'] for name, m in parsed.items()}
            if not timeline or timeline[-1]['states'] != states:
                timeline.append({'at': at, 'step': step, 'states': states,
                    'primary': next((name for name, m in parsed.items() if m['state'] == 'PRIMARY'), None)})

    for step in document['steps']:
        name, result = step['step'], step['result']
        at = timestamp(step['executedAt'])
        command = step.get('command') or {}
        if not isinstance(command, dict):
            command = {}
        config = command.get('replSetReconfig')
        if isinstance(config, dict) and isinstance(result, dict) and result.get('ok') == 1:
            for member in config.get('members', []):
                if isinstance(member, dict) and isinstance(member.get('host'), str):
                    priorities[member['host']] = member.get('priority')
        if isinstance(result, dict):
            if isinstance(result.get('set'), str):
                set_name = result['set']
            if result.get('errmsg') or result.get('error'):
                issues.append({'step': name, 'message': str(result.get('errmsg') or result.get('error'))[:1000]})
            members = result.get('members')
            if isinstance(members, list) and members and isinstance(members[0], dict) and 'host' in members[0]:
                for member in members:
                    if isinstance(member, dict) and isinstance(member.get('host'), str):
                        priorities[member['host']] = member.get('priority')
            else:
                capture(members, at, name)
            if result and all(isinstance(v, dict) and 'state' in v for v in result.values()):
                capture(result, at, name)
            if isinstance(result.get('predicted'), str) and isinstance(result.get('elected'), str):
                prediction = {'predicted': result['predicted'], 'elected': result['elected'], 'correct': result['predicted'] == result['elected']}
        elif isinstance(result, list):
            for row in result:
                if not isinstance(row, dict):
                    continue
                if 'members' in row:
                    capture(row['members'], timestamp(row.get('at', step['executedAt'])), name)
                if 'servedBy' in row:
                    reads.append({'at': timestamp(row.get('at', step['executedAt'])),
                        'servedBy': row['servedBy'] if isinstance(row['servedBy'], str) else None,
                        'error': str(row['error'])[:1000] if row.get('error') else None})
            if command.get('find') == 'messages' and isinstance(command.get('directConnection'), str):
                replication.append({'member': command['directConnection'], 'found': bool(result)})
    for name, member in final_members.items():
        if member['priority'] is None:
            member['priority'] = priorities.get(name)
    members = list(final_members.values())
    if not members:
        raise ValueError('No recorded replica member states found. Upload the completed script output.')
    return {'id': activity_id, 'title': title, 'script': document['script'],
        'recordedAt': max(timestamp(s['executedAt']) for s in document['steps']),
        'setName': set_name, 'members': members, 'timeline': timeline,
        'reads': reads, 'readSuccess': sum(bool(r['servedBy']) and not r['error'] for r in reads),
        'readFailure': sum(not r['servedBy'] or bool(r['error']) for r in reads),
        'replication': replication, 'prediction': prediction, 'issues': issues,
        'stepCount': len(document['steps']), 'mode': 'recorded'}


def import_run(db, document):
    raw = validate(document)
    summary = summarize(document)
    run_id = summary['id']
    uploaded = datetime.now(timezone.utc).isoformat()
    # Four bounded documents, one latest uploaded run per activity. _id is indexed.
    # Keep Extended JSON as a string, not executable queries or dotted MongoDB keys.
    db.replica_lab_runs.replace_one({'_id': run_id}, {'_id': run_id,
        'summary': summary, 'rawJson': raw, 'uploadedAt': uploaded,
        'sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest()}, upsert=True)
    return {'id': run_id, 'uploadedAt': uploaded, 'summary': summary}


def list_runs(db):
    rows = {r['_id']: r for r in db.replica_lab_runs.find({}, {'rawJson': 0})}
    return {'mode': 'recorded', 'activities': [
        {'id': id_, 'title': title, 'script': script,
         'run': rows.get(id_)} for script, (id_, title) in ACTIVITIES.items()]}


def get_run(db, run_id):
    if run_id not in {x[0] for x in ACTIVITIES.values()}:
        return None
    result = db.replica_lab_runs.find_one({'_id': run_id})
    if result:
        result['document'] = json.loads(result.pop('rawJson'))
    return result
