"""HTTP integration tests with a disposable MongoDB mock; no user database touched."""
import importlib, json, threading, unittest, urllib.request, urllib.error
from datetime import datetime, timezone
from unittest.mock import patch
try:
    import mongomock
except ImportError:
    mongomock=None

@unittest.skipIf(mongomock is None, 'Install requirements-dev.txt for HTTP integration tests')
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend import server, db, ingest, investigation, labs, monitor, alerts
        cls.server=server;cls.database=mongomock.MongoClient().signal_test;cls.patches=[]
        for module in (server,db,ingest,investigation,labs,monitor,alerts):
            p=patch.object(module,'db',cls.database);p.start();cls.patches.append(p)
        ingest.seed();investigation.migrate_entities()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.http.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close()
        for p in reversed(cls.patches):p.stop()
    def request(self,path,body=None):
        request=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:return json.load(response)
    def test_indicator_search_and_year_source_filters(self):
        d=self.request('/api/reports?q=lab-c2.example.invalid')
        self.assertEqual(d['total'],1)
        r=self.database.reports.find_one({'kind':'annual-report'})
        d=self.request('/api/reports?source='+r['sourceId']+'&year='+str(r['year'])+'&sort=year')
        self.assertGreater(d['total'],0)
        self.assertTrue(all(x['sourceId']==r['sourceId'] and x['year']==r['year'] for x in d['items']))
    def test_review_history_labels_seed_preservation(self):
        from backend.ingest import seed
        r=self.database.reports.find_one({'kind':'annual-report'});rid=r['_id']
        body={'category':'malware','verdict':'needs-review','note':'Test-only research label; not a confirmed incident.','entities':['Test entity','test ENTITY']}
        self.request('/api/review/'+rid,body);seed()
        updated=self.request('/api/reports/'+rid)
        self.assertEqual(updated['assessment']['note'],body['note'])
        self.assertEqual(updated['analystEntities'],['Test entity'])
        self.assertGreaterEqual(len(updated['reviewHistory']),1)
        profile=self.request('/api/entity?name=Test%20entity')
        self.assertEqual(profile['total'],1)
        self.assertTrue(any(x['name']=='Test entity' for x in self.request('/api/entities')))
    def test_pdf_evidence_in_report_search(self):
        r=self.database.reports.find_one({'kind':'annual-report'})
        self.database.evidence_passages.replace_one({'_id':'fixture'},{'_id':'fixture','reportId':r['_id'],'page':7,'text':'Exact evidence CVE-2025-99999','title':r['title'],'url':r['url']},upsert=True)
        d=self.request('/api/evidence?q=CVE-2025-99999')
        self.assertEqual(d['items'][0]['page'],7)
        self.assertEqual(self.request('/api/reports?q=CVE-2025-99999')['total'],1)
    def test_publication_date_filter_omits_undated_metadata(self):
        rid='date-test'
        self.database.reports.replace_one({'_id':rid},{'_id':rid,'sourceId':'none','publishedAt':datetime(2026,10,4,tzinfo=timezone.utc),'ingestedAt':datetime.now(timezone.utc)},upsert=True)
        d=self.request('/api/reports?from=2026-10-04&to=2026-10-04')
        self.assertEqual([r['_id'] for r in d['items']],[rid])
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/reports?from=2026-10-05&to=2026-10-04')
        self.assertEqual(e.exception.code,400)
    def test_invalid_labels_rejected(self):
        r=self.database.reports.find_one({'kind':'annual-report'})
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/review/'+r['_id'],{'category':'general','verdict':'needs-review','note':'A valid length note.','entities':'not an array'})
        self.assertEqual(e.exception.code,400)
    def test_alert_acknowledge_reopen_and_unassessed_filter(self):
        from backend.alerts import analyze_report
        r=self.database.reports.find_one({'kind':'annual-report'});rid=r['_id']
        self.database.evidence_passages.replace_one({'_id':'alert-fixture'},{'_id':'alert-fixture','reportId':rid,'page':9,'text':'This vulnerability was actively exploited in the wild.'},upsert=True)
        analyze_report(rid)
        d=self.request('/api/alerts?level=critical')
        self.assertTrue(any(x['_id']==rid for x in d['items']))
        self.request('/api/alerts/'+rid,{'status':'acknowledged'})
        self.assertFalse(any(x['_id']==rid for x in self.request('/api/alerts')['items']))
        self.assertTrue(any(x['_id']==rid for x in self.request('/api/alerts?ack=1')['items']))
        self.request('/api/alerts/'+rid,{'status':'open'})
        self.assertTrue(any(x['_id']==rid for x in self.request('/api/alerts')['items']))
        d=self.request('/api/reports?level=not-assessed')
        self.assertGreater(d['total'],0)
        self.assertTrue(all(not x.get('triage') or x['triage']['level']=='not-assessed' for x in d['items']))
    def test_processing_controls_persist(self):
        self.assertFalse(self.request('/api/processing',{'action':'pause'})['enabled'])
        self.assertFalse(self.request('/api/processing')['enabled'])
        self.assertTrue(self.request('/api/processing',{'action':'start'})['enabled'])
if __name__=='__main__':unittest.main()
