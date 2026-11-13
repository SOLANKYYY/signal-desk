import unittest
from unittest.mock import patch
import mongomock
from backend import intelligence as m
class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.db=mongomock.MongoClient().test
        self.p=patch.object(m,'db',self.db);self.p.start();self.addCleanup(self.p.stop)
        self.eid='55b7c901-614c-44d1-a638-440e950d210b'
        self.db.threat_events.insert_one({'_id':self.eid,'title':'Fixture <script>','source':'Example','timestamp':'2025-01-01T00:00:00+00:00'})
        self.db.threat_records.insert_one({'_id':'one','id':'one','event_id':self.eid,'indicator':'fixture.invalid','source':'Example','timestamp':'2025-01-01T00:00:00+00:00'})
    def test_exact_indicator_search_and_source_filter(self):
        self.assertEqual(m.events({'q':'fixture.invalid'})['total'],1)
        self.assertEqual(m.events({'q':'fixture.invalid','source':'Other'})['total'],0)
    def test_export_real_count_no_padding(self):
        r=m.exports({'limit':'15000'});self.assertEqual(r['count'],1);self.assertEqual(r['records'][0]['id'],'one')
    def test_message_never_fetches_urls(self):
        with patch.object(m.urllib.request,'urlopen',side_effect=AssertionError('unexpected fetch')):
            r=m.check_message('Urgent send OTP https://fixture.invalid/')
        self.assertEqual(len(r['links']),1);self.assertFalse(r['externalRequests'])
    def test_cases_persist_and_update(self):
        r=m.save_case({'title':'Research','note':'Unverified'});m.save_case({'id':r['_id'],'title':'Research','status':'closed'})
        self.assertEqual(self.db.intel_cases.count_documents({}),1)
        self.assertEqual(self.db.intel_cases.find_one()['status'],'closed')
    def test_vt_invalid_hash_rejected_before_request(self):
        with self.assertRaises(ValueError):m.vt_lookup('https://localhost/')
    def test_vt_missing_key_is_not_clean_verdict(self):
        with patch.dict(m.os.environ,{'VIRUSTOTAL_API_KEY':''}):self.assertFalse(m.vt_lookup('a'*64)['available'])
    def test_snapshot_upserts_do_not_overwrite(self):
        calls=[]
        with patch.object(self.db.threat_records,'bulk_write',side_effect=lambda ops,**kw:calls.extend(ops)):
            m.seed_snapshot();m.seed_snapshot()
        self.assertEqual(len(calls),15000)
        self.assertTrue(all('$setOnInsert' in op._doc for op in calls))
        self.assertEqual(self.db.import_state.count_documents({'_id':'public-threat-snapshot-v1'}),1)
if __name__=='__main__':unittest.main()
