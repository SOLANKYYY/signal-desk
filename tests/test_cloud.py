"""Cloud contract tests: isolated database and mocked queue, never real credentials."""
import base64, os, unittest
from datetime import timedelta
from unittest.mock import patch
try:
    import mongomock
    from backend import cloud,web
except ImportError: mongomock=None

@unittest.skipIf(mongomock is None,'Install development dependencies')
class CloudTests(unittest.TestCase):
    def setUp(self):
        from backend import db,alerts,server,investigation,ingest,labs,monitor
        self.store=mongomock.MongoClient().cloud_test
        self.patches=[]
        for m in (db,cloud,web,alerts,server,investigation,ingest,labs,monitor):
            p=patch.object(m,'db',self.store);p.start();self.patches.append(p)
        self.env=patch.dict(os.environ,{'APP_PASSWORD':'test-password-long-enough','APP_USERNAME':'admin','MONGODB_URI':'mongodb://127.0.0.1:27017','CRON_SECRET':'x'*32,'VERCEL':'1'})
        self.env.start();self.addCleanup(self.env.stop)
        for p in self.patches:self.addCleanup(p.stop)
        self.store.import_state.insert_one({'_id':'cloud-schema','version':1})
        self.api=web.app.test_client()
        self.auth={'Authorization':'Basic '+base64.b64encode(b'admin:test-password-long-enough').decode()}
    def report(self,i='r1'):
        self.store.reports.insert_one({'_id':i,'kind':'annual-report','title':'Test report','year':2026,'provenance':{'synthetic':False},'sourceId':'source','assessment':{'verdict':'needs-review'}})
    def test_auth_required_for_html_and_api_and_missing_password_fails_closed(self):
        self.assertEqual(self.api.get('/').status_code,401)
        self.assertEqual(self.api.get('/api/reports').status_code,401)
        self.assertEqual(self.api.get('/',headers=self.auth).status_code,200)
        with patch.dict(os.environ,{'APP_PASSWORD':''}):self.assertEqual(self.api.get('/').status_code,503)
    def test_cross_origin_and_local_only_jobs_blocked(self):
        r=self.api.post('/api/processing',json={'action':'start'},headers={**self.auth,'Origin':'https://unrelated.invalid'})
        self.assertEqual(r.status_code,403)
        r=self.api.post('/api/jobs/generate',json={},headers=self.auth)
        self.assertEqual(r.status_code,400)
    def test_bridge_reads_and_review_writes_preserve_contract(self):
        self.report()
        self.assertEqual(self.api.get('/api/reports',headers=self.auth).json['total'],1)
        r=self.api.post('/api/review/r1',json={'category':'general','verdict':'needs-review','note':'Cloud analyst evidence note','entities':[]},headers=self.auth)
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.store.reports.find_one()['assessment']['note'],'Cloud analyst evidence note')
    def test_start_is_deduplicated_and_pause_invalidates_chain(self):
        self.report()
        with patch.object(cloud,'publish') as send:
            cloud.kick_auto();cloud.kick_auto();self.assertEqual(send.call_count,1)
            message=send.call_args.args[0]
            cloud.control('pause')
            with patch.object(cloud.processor,'process_one') as process:
                cloud.work(message);process.assert_not_called()
            cloud.control('start');self.assertEqual(send.call_count,2)
    def test_completed_catalog_does_not_publish_idle_work(self):
        self.report();self.store.reports.update_one({'_id':'r1'},{'$set':{'pdf.status':'indexed','triage.version':'report-triage-v1'}})
        with patch.object(cloud,'publish') as send:cloud.kick_auto();send.assert_not_called()
    def test_queue_state_survives_request_and_retries_do_not_repeat_completed_step(self):
        self.report()
        with patch.object(cloud,'publish') as send:
            cloud.kick_auto();message=send.call_args.args[0]
            def process():self.store.reports.update_one({'_id':'r1'},{'$set':{'pdf.status':'indexed','triage.version':'report-triage-v1'}})
            with patch.object(cloud.processor,'process_one',side_effect=process) as fn:
                cloud.work(message);cloud.work(message);self.assertEqual(fn.call_count,1)
        self.assertFalse(self.store.import_state.find_one({'_id':'cloud-chain'})['active'])
    def test_cloud_jobs_queue_and_store_result_without_threads(self):
        with patch.object(cloud,'publish') as send:
            r=self.api.post('/api/jobs/sync',json={},headers=self.auth)
            self.assertEqual(r.status_code,202)
            message=send.call_args.args[0]
            with patch('backend.ingest.sync_all',return_value=[{'source':'annual','status':'ok'}]):cloud.work(message)
        jobs=self.api.get('/api/jobs',headers=self.auth).json
        self.assertEqual(jobs[0]['status'],'completed')
        self.assertEqual(jobs[0]['result']['results'][0]['status'],'ok')
    def test_cron_requires_its_own_secret(self):
        self.assertEqual(self.api.get('/api/cron',headers=self.auth).status_code,401)
        with patch.object(cloud,'publish'):
            r=self.api.get('/api/cron',headers={'Authorization':'Bearer '+'x'*32})
            self.assertEqual(r.status_code,202)
    def test_expired_job_unlocks_retry_and_late_delivery_is_ignored(self):
        with patch.object(cloud,'publish') as send:
            job,_=cloud.enqueue_job('sync',{})
            message=send.call_args.args[0]
            self.store.cloud_jobs.update_one({'_id':job['_id']},{'$set':{'expiresAt':cloud.now()-timedelta(seconds=1)}})
            self.assertEqual(self.api.get('/api/jobs',headers=self.auth).json[0]['status'],'failed')
            with patch('backend.ingest.sync_all') as sync:
                cloud.work(message);sync.assert_not_called()
            _,status=cloud.enqueue_job('sync',{})
            self.assertEqual(status,202)
    def test_cloud_results_persist_to_database(self):
        from backend.labs import save
        save('schema_sizes.json',{'collections':[]})
        self.assertEqual(self.api.get('/api/results',headers=self.auth).json,{'schema_sizes.json':{'collections':[]}})
if __name__=='__main__':unittest.main()
