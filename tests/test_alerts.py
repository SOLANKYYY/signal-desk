import unittest
from unittest.mock import patch
from backend.alerts import evaluate, analyze_report, Processor
try:
    import mongomock
except ImportError: mongomock=None

class RuleTests(unittest.TestCase):
    def report(self):return {'kind':'annual-report','provenance':{'synthetic':False},'year':2022}
    def test_metadata_and_fictional_reports_never_raise_alerts(self):
        r=self.report();r['title']='Actively exploited ransomware attack';r['summary']=r['title']*10
        self.assertEqual(evaluate(r,[])['level'],'not-assessed')
        r['provenance']['synthetic']=True
        self.assertFalse(evaluate(r,[{'text':'Actively exploited in the wild.','page':3}])['alert'])
    def test_levels_evidence_and_historical_context(self):
        for text,level in [('Attackers actively exploited this flaw.','critical'),('The ransomware attack involved credential theft.','high'),('A phishing campaign was described.','medium'),('This publication discusses governance.','low')]:
            result=evaluate(self.report(),[{'text':text,'page':7}])
            self.assertEqual(result['level'],level)
            self.assertEqual(result['alert'],level in ('critical','high'))
            self.assertEqual(result['historicalYear'],2022)
            if result['basis']:self.assertEqual(result['basis'][0]['page'],7)
    def test_negated_and_hypothetical_claims_do_not_create_alerts(self):
        for text in ['This vulnerability is not actively exploited.','There is no evidence of data exfiltration.','A hypothetical ransomware attack was simulated.']:
            self.assertFalse(evaluate(self.report(),[{'text':text,'page':1}])['alert'])
    def test_summary_requires_substantial_source_text(self):
        r={'kind':'article','summary':'A ransomware attack','provenance':{}}
        self.assertEqual(evaluate(r,[])['level'],'not-assessed')
        r['summary']='A ransomware attack was reported. '+('The original publisher described the affected systems and recovery procedures. '*2)
        self.assertEqual(evaluate(r,[])['level'],'high')

@unittest.skipIf(mongomock is None,'Install requirements-dev.txt')
class QueueTests(unittest.TestCase):
    def setUp(self):
        self.db=mongomock.MongoClient().queue_test
        self.patcher=patch('backend.alerts.db',self.db);self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.db.reports.insert_many([{'_id':str(i),'title':'Report '+str(i),'kind':'annual-report','year':2026-i,'provenance':{},'assessment':{'verdict':'benign','note':'Saved analyst note'}} for i in range(2)])
    def test_queue_failure_retry_resume_and_preservation(self):
        q=Processor()
        with patch('backend.investigation.index_pdf',side_effect=ValueError('Unreadable PDF')):self.assertTrue(q.process_one())
        self.assertEqual(q.status()['failed'],1)
        q.control('pause');self.assertFalse(Processor().enabled())
        q.control('retry');self.assertEqual(q.status()['failed'],0)
        def indexed(rid):
            self.db.reports.update_one({'_id':rid},{'$set':{'pdf':{'status':'indexed'}}})
            self.db.evidence_passages.insert_one({'reportId':rid,'page':4,'text':'Data exfiltration followed a ransomware attack.'})
        with patch('backend.investigation.index_pdf',side_effect=indexed) as download:
            self.assertTrue(q.process_one());self.assertTrue(Processor().process_one());self.assertFalse(q.process_one())
            self.assertEqual(download.call_count,2)
        self.assertEqual(q.status()['indexed'],2)
        self.assertEqual(q.status()['remaining'],0)
        for report in self.db.reports.find():
            self.assertEqual(report['triage']['level'],'high')
            self.assertEqual(report['assessment']['note'],'Saved analyst note')
            self.assertEqual(report['assessment']['verdict'],'benign')
    def test_interrupted_running_report_is_resumable(self):
        self.db.reports.update_one({'_id':'0'},{'$set':{'processing':{'status':'running'}}})
        with patch('backend.investigation.index_pdf',side_effect=ValueError('Retry observed')) as f:Processor().process_one()
        f.assert_called_once_with('0')
if __name__=='__main__':unittest.main()
