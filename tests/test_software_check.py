import unittest
from backend.software_check import review
from backend.device_check import analyze
from test_device_check import report

class SoftwareChecks(unittest.TestCase):
    def inventory(self,product,version):return {'available':True,'items':[{'product':product,'version':version,'evidence':'file_version'}]}
    def test_verified_versions_match_three_unique_cves(self):
        r=report();r['software']={'available':True,'items':[{'product':'oracle_java_8','version':'8.0.2510.8','evidence':'file_version'},{'product':'teamviewer','version':'15.50.5.0','evidence':'file_version'}]}
        a=analyze(r);self.assertEqual(a['counts']['matched_cves'],3);self.assertEqual(a['counts']['affected_products'],2);self.assertEqual(a['counts']['active_defender_detections'],0)
    def test_teamviewer_fixed_branches_not_flagged(self):
        for v in ['15.58.4','15.58.4.0','15.99.0','14.7.48796','13.2.36225','12.0.259312','11.0.259311']:
            self.assertEqual(review(self.inventory('teamviewer',v))['matches'],[],v)
        self.assertEqual(len(review(self.inventory('teamviewer','14.7.48795'))['matches']),1)
    def test_java_exact_advisory_match_only_and_unknown_not_clean(self):
        for v in ['8.0.2610.12','8.0.2410.7']:
            a=review(self.inventory('oracle_java_8',v));self.assertEqual(a['matches'],[]);self.assertIn('No match is not',a['coverage'])
    def test_invalid_and_duplicate_records(self):
        with self.assertRaises(ValueError):review(self.inventory('teamviewer','15.2; run command'))
        with self.assertRaises(ValueError):review(self.inventory('untrusted product','15.2'))
        a=self.inventory('teamviewer','15.50.5');a['items']*=2;self.assertEqual(len(review(a)['matches']),1)
    def test_unrecognized_fields_are_not_forwarded(self):
        a=self.inventory('teamviewer','15.50.5');a['items'][0]['path']='SECRET';a['instructions']='SECRET'
        self.assertNotIn('SECRET',str(review(a)))

if __name__=='__main__':unittest.main()
