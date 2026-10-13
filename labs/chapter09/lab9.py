"""Exercise 9: measurements against an isolated, local three-node Docker set."""
import json
import os
from pathlib import Path
import statistics
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4
from pymongo import MongoClient, ReadPreference
from pymongo.errors import OperationFailure, PyMongoError
from pymongo.write_concern import WriteConcern

HOSTS = [f'sd9-mongo{i}:27017' for i in range(1, 4)]
OUT = Path(os.getenv('RESULTS_DIR', '/results'))


def now():
    return datetime.now(timezone.utc).isoformat()


def client(host=None):
    # Bounded waits let this teaching experiment record failures during partitions.
    # Disable automatic write retry so a probe represents exactly one attempt.
    return MongoClient(host or ('mongodb://' + ','.join(HOSTS) + '/?replicaSet=sd9'),
                       directConnection=bool(host), retryWrites=False,
                       serverSelectionTimeoutMS=3000, connectTimeoutMS=2000,
                       socketTimeoutMS=7000, appname='SignalDeskExercise9')


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / name
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(target)


def load(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def healthy(c, timeout=120, observe=None):
    end = time.monotonic() + timeout
    last = 'Waiting for election'
    while time.monotonic() < end:
        if observe: observe()
        try:
            s = c.admin.command('replSetGetStatus')
            members = s['members']
            if len(members) == 3 and all(m['health'] == 1 for m in members) and sorted(m['stateStr'] for m in members) == ['PRIMARY', 'SECONDARY', 'SECONDARY']:
                return s
            last = str([(m['name'], m['stateStr']) for m in members])
        except PyMongoError as exc:
            last = str(exc)
        time.sleep(1)
    raise RuntimeError('Replica set did not become healthy: ' + last)


def initialize():
    deadline = time.monotonic() + 120
    for host in HOSTS:
        with client(host) as node:
            while True:
                try:
                    node.admin.command('ping')
                    break
                except PyMongoError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(1)
    with client(HOSTS[0]) as direct:
        try:
            direct.admin.command('replSetInitiate', {'_id': 'sd9', 'members': [
                {'_id': i, 'host': h} for i, h in enumerate(HOSTS)]})
        except OperationFailure as exc:
            if exc.code != 23:  # AlreadyInitialized is safe on subsequent runs.
                raise
    with client() as c:
        healthy(c)
        cfg = c.admin.command('replSetGetConfig')['config']
        if len(cfg['members']) != 3 or any(m.get('arbiterOnly') for m in cfg['members']) or {m['host'] for m in cfg['members']} != set(HOSTS):
            raise RuntimeError('Use this kit’s isolated three-data-node replica set.')
    print('Exercise 9 replica set ready: three data-bearing members, no arbiter.')


def envelope(activity):
    return {'format': 'signal-desk-exercise9', 'version': 1, 'activity': activity,
            'startedAt': now(), 'runId': uuid4().hex, 'topology': HOSTS}


def benchmark():
    result = envelope('latency')
    result['rows'] = []
    with client() as c:
        healthy(c)
        result['mongoVersion'] = c.server_info()['version']
        result['majorityJournalDefault'] = c.admin.command('replSetGetConfig')['config'].get('writeConcernMajorityJournalDefault', True)
        print('6 configurations x 1,000 individual writes. Journal tests may take several minutes.', flush=True)
        for w in (1, 'majority', 3):
            for journal in (False, True):
                coll = c.exercise9.get_collection('latency_' + result['runId'], write_concern=WriteConcern(w=w, j=journal, wtimeout=5000))
                # Warm the connection and collection outside the timed sample.
                coll.insert_one({'warmup': True, 'w': w, 'j': journal})
                samples = []
                started = time.perf_counter()
                for i in range(1000):
                    tick = time.perf_counter()
                    coll.insert_one({'run': result['runId'], 'sequence': i, 'w': w, 'j': journal, 'payload': 'x' * 128})
                    samples.append((time.perf_counter() - tick) * 1000)
                elapsed = (time.perf_counter() - started) * 1000
                result['rows'].append({'w': w, 'j': journal, 'count': 1000, 'elapsedMs': elapsed, 'samplesMs': samples})
                print(f'w={str(w):8} j={str(journal):5} total={elapsed:.1f}ms average={statistics.mean(samples):.3f}ms p50={statistics.median(samples):.3f}ms p99={sorted(samples)[989]:.3f}ms', flush=True)
    result['finishedAt'] = now()
    save('lab_9_1_latency.json', result)
    print('Saved results/lab_9_1_latency.json')


def snapshot(c, phase, origin):
    event = {'at': now(), 'elapsedSeconds': round(time.monotonic() - origin, 3), 'phase': phase, 'kind': 'status'}
    try:
        status = c.admin.command('replSetGetStatus')
        event['members'] = [{'name': m['name'], 'state': m['stateStr'], 'health': m['health']} for m in status['members']]
    except PyMongoError as exc:
        event['error'] = type(exc).__name__ + ': ' + str(exc)[:600]
    return event


def probes(c, phase, origin, run_id):
    events = []
    for w in (1, 'majority'):
        tick = time.perf_counter()
        event = {'at': now(), 'elapsedSeconds': round(time.monotonic() - origin, 3), 'phase': phase, 'kind': 'write', 'w': w}
        try:
            c.exercise9.get_collection('partition', write_concern=WriteConcern(w=w, j=True, wtimeout=2000)).insert_one({'run': run_id, 'phase': phase, 'at': now(), 'w': w})
            event['outcome'] = 'acknowledged'
        except PyMongoError as exc:
            # A timeout is an acknowledgment failure; the write may still exist.
            event['outcome'] = type(exc).__name__
            event['error'] = str(exc)[:600]
        event['latencyMs'] = round((time.perf_counter() - tick) * 1000, 3)
        events.append(event)
    return events


def plan(c):
    state = healthy(c)
    primary = next(m['name'] for m in state['members'] if m['stateStr'] == 'PRIMARY')
    data = {'primary': primary, 'secondaries': [h.split(':')[0] for h in HOSTS if h != primary]}
    save('partition-plan.json', data)
    return data


def partition_start():
    result = envelope('partition')
    with client() as c:
        p = plan(c)
    result.update(observer=p['primary'], events=[])
    save('partition-progress.json', result)
    print('Recording from initial primary:', p['primary'])
    partition_phase('baseline', 1)


def partition_phase(phase, seconds):
    result = load('partition-progress.json')
    p = load('partition-plan.json')
    origin = time.monotonic()
    with client(p['primary']) as c:
        result['events'].append(snapshot(c, phase, origin))
        result['events'].extend(probes(c, phase, origin, result['runId']))
        while time.monotonic() - origin < seconds:
            result['events'].append(snapshot(c, phase, origin))
            time.sleep(1)
        result['events'].extend(probes(c, phase, origin, result['runId']))
        result['events'].append(snapshot(c, phase, origin))
    save('partition-progress.json', result)
    print(phase, ': observation finished; inspect actual outcomes in the JSON.')


def recover(phase):
    result = load('partition-progress.json')
    prior = load('partition-plan.json')['primary']
    origin = time.monotonic()
    with client() as c, client(prior) as observer:
        healthy(c, observe=lambda: result['events'].append(snapshot(observer, phase, origin)))
        p = plan(c)
        # A w:3 sentinel plus direct reads verifies catch-up beyond rs.status health.
        marker = uuid4().hex
        c.exercise9.get_collection('recovery', write_concern=WriteConcern(w=3, j=True, wtimeout=15000)).insert_one({'_id': marker})
        found = []
        for h in HOSTS:
            with client(h) as direct:
                coll = direct.exercise9.get_collection('recovery', read_preference=ReadPreference.SECONDARY_PREFERRED)
                deadline = time.monotonic() + 15
                present = bool(coll.find_one({'_id': marker}))
                while not present and time.monotonic() < deadline:
                    time.sleep(0.2)
                    present = bool(coll.find_one({'_id': marker}))
                found.append(present)
        if not all(found):
            raise RuntimeError('Recovery sentinel is missing on a member. Retry recovery.')
        event = snapshot(c, phase, origin)
        event.update(kind='recovery', caughtUp=True, sentinel=marker)
        result['events'].append(event)
        result['observer'] = p['primary']
    save('partition-progress.json', result)
    print('Recovery verified: sentinel present on all three members.')


def finish():
    result = load('partition-progress.json')
    required = {'baseline', 'one-secondary-offline', 'first-recovery', 'two-secondaries-offline', 'final-recovery'}
    if not required.issubset({e['phase'] for e in result['events']}) or result['events'][-1].get('caughtUp') is not True:
        raise RuntimeError('Partition experiment incomplete. Run run-partition.ps1 again.')
    result['finishedAt'] = now()
    save('lab_9_2_partition.json', result)
    print('Saved results/lab_9_2_partition.json')


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if action == 'init': initialize()
    elif action == 'latency': benchmark()
    elif action == 'partition-start': partition_start()
    elif action == 'phase' and len(sys.argv) == 4 and sys.argv[2] in ('one-secondary-offline', 'two-secondaries-offline'):
        partition_phase(sys.argv[2], max(30, min(60, int(sys.argv[3]))))
    elif action == 'recover' and len(sys.argv) == 3 and sys.argv[2] in ('first-recovery', 'final-recovery'): recover(sys.argv[2])
    elif action == 'finish': finish()
    else: print('Commands: init | latency | partition-start | phase <phase> 30 | recover <phase> | finish. See README.md.')
