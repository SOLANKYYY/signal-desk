"""Replica lab parsing and hosted API tests use isolated, in-memory storage."""
import base64
import os
import unittest
from unittest.mock import patch
import mongomock
from backend import replica_lab, server, web

AT = {'$date': '2026-10-13T13:27:51Z'}


def step(name, result, command=None):
    return {'step': name, 'executedAt': AT, 'result': result, 'command': command}


def result_file(script='lab_8_1_replica_set.py'):
    return {'activity': 'Isolated test fixture', 'script': script, 'steps': [step('Final rs.status()', {
        'set': 'rs0', 'members': [
            {'name': 'mongo1:27017', 'stateStr': 'PRIMARY', 'health': 1},
            {'name': 'mongo2:27017', 'stateStr': 'SECONDARY', 'health': 1},
            {'name': 'mongo3:27017', 'stateStr': 'SECONDARY', 'health': 1}]})]}


class ReplicaLabTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().replica_tests

    def test_empty_and_idempotent_import_do_not_touch_cti(self):
        self.assertTrue(all(a['run'] is None for a in replica_lab.list_runs(self.db)['activities']))
        doc = result_file()
        for _ in range(2):
            replica_lab.import_run(self.db, doc)
        self.assertEqual(self.db.replica_lab_runs.count_documents({}), 1)
        self.assertEqual(self.db.list_collection_names(), ['replica_lab_runs'])
        stored = replica_lab.get_run(self.db, 'replication')
        self.assertEqual(stored['document'], doc)
        self.assertEqual(stored['summary']['members'][0]['state'], 'PRIMARY')
        self.assertEqual(stored['summary']['mode'], 'recorded')
        self.assertIsNone(replica_lab.get_run(self.db, 'missing'))
        self.assertNotIn('rawJson', replica_lab.list_runs(self.db)['activities'][0]['run'])

    def test_failover_reads_and_recorded_states(self):
        doc = result_file('lab_8_2_failover_monitor.py')
        doc['steps'].insert(0, step('Continuous reads', [
            {'at': AT, 'servedBy': 'mongo1:27017', 'document': {'text': 'test'}},
            {'at': AT, 'servedBy': None, 'error': 'Election underway'},
            {'at': AT, 'servedBy': 'mongo2:27017', 'document': {'text': 'test'}}]))
        doc['steps'].insert(1, step('Election', [
            {'at': AT, 'members': {'mongo1:27017': 'PRIMARY', 'mongo2:27017': 'SECONDARY'}},
            {'at': AT, 'members': {'mongo1:27017': 'SECONDARY', 'mongo2:27017': 'PRIMARY'}}]))
        summary = replica_lab.import_run(self.db, doc)['summary']
        self.assertEqual((summary['readSuccess'], summary['readFailure']), (2, 1))
        self.assertEqual([t['primary'] for t in summary['timeline']][:2], ['mongo1:27017', 'mongo2:27017'])
        self.assertEqual(summary['members'][0]['state'], 'PRIMARY')

    def test_priority_prediction_is_calculated_not_trusted(self):
        doc = result_file('try_8_2_priority_election.py')
        doc['steps'].insert(0, step('Set priorities', {'ok': 1}, {'replSetReconfig': {'members': [
            {'host': 'mongo1:27017', 'priority': 3}, {'host': 'mongo2:27017', 'priority': 2}]}}))
        doc['steps'].append(step('Verify', {'predicted': 'mongo2:27017', 'elected': 'mongo3:27017', 'prediction': 'CORRECT'}))
        s = replica_lab.import_run(self.db, doc)['summary']
        self.assertFalse(s['prediction']['correct'])
        self.assertEqual(s['members'][0]['priority'], 3)

    def test_replication_empty_reads_and_handled_errors_are_visible(self):
        doc = result_file()
        doc['steps'].insert(0, step('Read secondary', [], {'find': 'messages', 'directConnection': 'mongo2:27017'}))
        doc['steps'].insert(1, step('First attempt', {'ok': 0, 'errmsg': 'Set write concern'}))
        doc['steps'].insert(2, step('Retry', {'ok': 1}))
        s = replica_lab.import_run(self.db, doc)['summary']
        self.assertFalse(s['replication'][0]['found'])
        self.assertEqual(len(s['issues']), 1)

    def test_invalid_files_rejected_without_writes(self):
        bad = [{}, {**result_file(), 'script': 'unrelated.py'}, {**result_file(), 'steps': []}]
        d = result_file(); d['steps'][0]['executedAt'] = 'bad-date'; bad.append(d)
        d = result_file(); d['padding'] = 'x' * replica_lab.MAX_UPLOAD; bad.append(d)
        d = result_file(); d['steps'][0]['result'] = {'ok': 1}; bad.append(d)
        d = result_file(); d['value'] = float('nan'); bad.append(d)
        for document in bad:
            with self.subTest(document=str(document)[:80]), self.assertRaises(ValueError):
                replica_lab.import_run(self.db, document)
        self.assertEqual(self.db.replica_lab_runs.count_documents({}), 0)

    def test_hosted_api_auth_limits_persistence_and_static_asset(self):
        auth = {'Authorization': 'Basic ' + base64.b64encode(b'admin:replica-test-password').decode()}
        with patch.dict(os.environ, {'APP_PASSWORD': 'replica-test-password', 'MONGODB_URI': 'mongodb://127.0.0.1', 'APP_USERNAME': 'admin'}), patch.object(server, 'db', self.db), patch.object(web.cloud, 'bootstrap'):
            api = web.app.test_client()
            self.assertEqual(api.post('/api/replica-lab/import', json=result_file()).status_code, 401)
            self.assertEqual(api.post('/api/replica-lab/import', json=result_file(), headers={**auth, 'Origin': 'https://wrong.invalid'}).status_code, 403)
            doc = result_file(); doc['notes'] = 'x' * 20000
            r = api.post('/api/replica-lab/import', json=doc, headers=auth)
            self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual(api.get('/api/replica-lab/replication', headers=auth).json['document'], doc)
            self.assertEqual(api.get('/api/replica-lab', headers=auth).json['activities'][0]['run']['_id'], 'replication')
            self.assertEqual(api.get('/api/replica-lab/unknown', headers=auth).status_code, 404)
            self.assertEqual(api.get('/replica-lab.js', headers=auth).status_code, 200)
            self.assertEqual(api.post('/api/replica-lab/import', json={'invalid': True}, headers=auth).status_code, 400)
            self.assertEqual(api.post('/api/replica-lab/import', data='x' * (replica_lab.MAX_UPLOAD+1), headers=auth).status_code, 413)
            self.assertEqual(api.post('/api/review/test', json=doc, headers=auth).status_code, 413)


if __name__ == '__main__':
    unittest.main()
