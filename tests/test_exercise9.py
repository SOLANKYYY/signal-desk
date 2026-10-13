"""Evidence validation and hosted routes use an isolated mock database."""
import base64
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
import zipfile
import mongomock
from backend import exercise9, server, web


def fixture(activity='latency'):
    doc = {'format': 'signal-desk-exercise9', 'version': 1, 'activity': activity,
           'topology': sorted(exercise9.HOSTS), 'startedAt': '2026-10-13T10:00:00Z', 'finishedAt': '2026-10-13T11:00:00Z'}
    if activity == 'latency':
        doc['rows'] = [{'w': w, 'j': j, 'count': 1000, 'elapsedMs': 1001, 'samplesMs': [1]*1000} for w in (1, 'majority', 3) for j in (False, True)]
    else:
        doc['events'] = []
        for phase in ('baseline', 'one-secondary-offline', 'first-recovery', 'two-secondaries-offline', 'final-recovery'):
            e = {'phase': phase, 'at': doc['startedAt'], 'elapsedSeconds': 30}
            for w in (1, 'majority'):
                doc['events'].append({**e, 'kind': 'write', 'w': w, 'latencyMs': 3, 'outcome': 'WTimeoutError' if phase=='two-secondaries-offline' else 'acknowledged'})
            doc['events'].append({**e, 'kind': 'recovery' if 'recovery' in phase else 'status', 'caughtUp': True,
                'members': [{'name': h, 'state': 'PRIMARY' if i==0 else 'SECONDARY', 'health': 1} for i,h in enumerate(sorted(exercise9.HOSTS))]})
    return doc


class Exercise9Tests(unittest.TestCase):
    def setUp(self):
        self.db=mongomock.MongoClient().exercise9_test

    def test_benchmark_derived_from_samples_and_latest_only(self):
        d=fixture();d['rows'][0]['averageMs']=999
        for _ in range(2): result=exercise9.import_run(self.db,d)
        self.assertEqual(result['summary']['rows'][0]['averageMs'],1)
        self.assertEqual(result['summary']['rows'][0]['p99Ms'],1)
        self.assertEqual(self.db.exercise9_runs.count_documents({}),1)
        self.assertEqual(exercise9.get_run(self.db,'latency')['document'],d)
        self.assertNotIn('rawJson',exercise9.list_runs(self.db)['runs'][0])
        self.assertEqual(self.db.list_collection_names(),['exercise9_runs'])

    def test_invalid_benchmarks_never_written(self):
        bad=[]
        for key,value in [('w','all'),('w',True),('j',1),('count',999),('samplesMs',[1]*999),('elapsedMs',3),('samplesMs',[float('nan')]*1000)]:
            d=fixture();d['rows'][0][key]=value;bad.append(d)
        d=fixture();d['rows'][1]=copy.deepcopy(d['rows'][0]);bad.append(d)
        d=fixture();d['topology'][0]={};bad.append(d)
        d=fixture();d['startedAt']='yesterday';bad.append(d)
        for d in bad:
            with self.subTest(d=str(d)[:80]),self.assertRaises(ValueError):exercise9.import_run(self.db,d)
        self.assertEqual(self.db.exercise9_runs.count_documents({}),0)

    def test_partition_preserves_failures_and_requires_recovery(self):
        d=fixture('partition');s=exercise9.import_run(self.db,d)['summary']
        self.assertEqual(s['failed'],2)
        self.assertEqual(s['acknowledged'],8)
        for mutate in ('missing','short','unsafe','duplicate'):
            bad=copy.deepcopy(d)
            if mutate=='missing':bad['events']=bad['events'][:-1]
            elif mutate=='short':
                for e in bad['events']:e['elapsedSeconds']=1
            elif mutate=='unsafe':bad['events'][0]['phase']={}
            else:bad['events'][-1]['members'][1]['name']=bad['events'][-1]['members'][0]['name']
            with self.assertRaises(ValueError):exercise9.validate(bad)

    def test_download_kit_contains_only_reviewed_source(self):
        with zipfile.ZipFile(io.BytesIO(exercise9.kit_bytes())) as z:
            self.assertEqual(len(z.namelist()),len(exercise9.KIT_FILES))
            self.assertTrue(all(n.startswith('SignalDesk_Exercise9/') for n in z.namelist()))
            self.assertNotIn('results/', '\n'.join(z.namelist()))
            self.assertIn(b'Invoke-Lab -LabArguments',z.read('SignalDesk_Exercise9/run-partition.ps1'))
            self.assertIn(b'/evidence/',z.read('SignalDesk_Exercise9/Dockerfile.submission'))

    def test_auth_size_origin_and_persistent_upload_routes(self):
        auth={'Authorization':'Basic '+base64.b64encode(b'admin:exercise9-test-password').decode()}
        with patch.dict(os.environ,{'APP_PASSWORD':'exercise9-test-password','APP_USERNAME':'admin','MONGODB_URI':'mongodb://127.0.0.1'}),patch.object(server,'db',self.db),patch.object(web.cloud,'bootstrap'):
            api=web.app.test_client()
            self.assertEqual(api.get('/api/exercise9/kit').status_code,401)
            self.assertEqual(api.post('/api/exercise9/import',json=fixture(),headers={**auth,'Origin':'https://elsewhere.invalid'}).status_code,403)
            self.assertEqual(api.get('/exercise9.js',headers=auth).status_code,200)
            self.assertEqual(api.get('/api/exercise9/kit',headers=auth).mimetype,'application/zip')
            for activity in ('latency','partition'):
                r=api.post('/api/exercise9/import',json=fixture(activity),headers=auth)
                self.assertEqual(r.status_code,201,r.data)
                self.assertEqual(api.get('/api/exercise9/'+activity,headers=auth).json['document'],fixture(activity))
            self.assertEqual(len(api.get('/api/exercise9',headers=auth).json['runs']),2)
            self.assertEqual(api.get('/api/exercise9/unknown',headers=auth).status_code,404)
            self.assertEqual(api.post('/api/exercise9/import',json={},headers=auth).status_code,400)
            self.assertEqual(api.post('/api/exercise9/import',data='x'*(exercise9.MAX_UPLOAD+1),headers=auth).status_code,413)

    def test_probe_error_is_evidence_not_false_success(self):
        spec=importlib.util.spec_from_file_location('lab9',Path(__file__).resolve().parents[1]/'labs/chapter09/lab9.py')
        lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)
        c=MagicMock()
        from pymongo.errors import WTimeoutError
        c.exercise9.get_collection.return_value.insert_one.side_effect=WTimeoutError('not acknowledged')
        import time
        events=lab.probes(c,'two-secondaries-offline',time.monotonic(),'isolated-test')
        self.assertEqual([e['outcome'] for e in events],['WTimeoutError','WTimeoutError'])
        self.assertEqual(c.exercise9.get_collection.return_value.insert_one.call_count,2)

if __name__=='__main__':unittest.main()
