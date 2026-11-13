import unittest
from tools.threat_feed import normalize_event,event_url
class FeedTests(unittest.TestCase):
    def event(self):
        return {'uuid':'55b7c901-614c-44d1-a638-440e950d210b','timestamp':'1700000000','Orgc':{'name':'Unit fixture'},'Attribute':[{'uuid':'55b7c948-fc10-48c4-9dfb-ce26950d210b','type':'domain','value':'fixture.invalid','timestamp':'1700000000','to_ids':True}]}
    def test_provenance_and_unit(self):
        r=normalize_event(self.event(),'circl')[0]
        self.assertEqual(r['target'],'fixture.invalid');self.assertEqual(r['record_unit'],'MISP indicator attribute')
        self.assertEqual(r['timestamp_basis'],'attribute modification time')
    def test_non_indicators_and_deleted_are_excluded(self):
        e=self.event();e['Attribute'][0]['type']='link';self.assertEqual(normalize_event(e,'circl'),[])
        e=self.event();e['Attribute'][0]['deleted']=True;self.assertEqual(normalize_event(e,'circl'),[])
    def test_missing_time_is_not_fabricated(self):
        e=self.event();del e['Attribute'][0]['timestamp'];self.assertEqual(normalize_event(e,'circl'),[])
    def test_path_injection_rejected(self):
        with self.assertRaises(ValueError):event_url('circl','../../private')
    def test_future_time_rejected(self):
        e=self.event();e['Attribute'][0]['timestamp']='9999999999';self.assertEqual(normalize_event(e,'circl'),[])
if __name__=='__main__':unittest.main()
