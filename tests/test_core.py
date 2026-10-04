import unittest
from backend.core import classify, cache_delta, parse_annual, safe_url
from backend.ingest import parse_feed
from backend.labs import make_workload_doc
from bson import BSON
class CoreTests(unittest.TestCase):
    def test_topic_does_not_claim_threat(self):
        x=classify('Ransomware report')
        self.assertEqual(x['category'],'ransomware');self.assertEqual(x['verdict'],'needs-review')
    def test_non_threat_content(self):
        self.assertEqual(classify('Security training newsletter')['category'],'general')
    def test_interval_formula(self):
        x=cache_delta({'pagesRequested':100,'pagesRead':10},{'pagesRequested':200,'pagesRead':30})
        self.assertAlmostEqual(x['hitRatioPct'],80)
    def test_counter_edges(self):
        self.assertIsNone(cache_delta(None,{'pagesRequested':2,'pagesRead':0})['hitRatioPct'])
        for p,c in [({'pagesRequested':5,'pagesRead':1},{'pagesRequested':5,'pagesRead':1}),
                    ({'pagesRequested':5,'pagesRead':1},{'pagesRequested':1,'pagesRead':0}),
                    ({'pagesRequested':1,'pagesRead':1},{'pagesRequested':2,'pagesRead':9})]:
            self.assertIsNone(cache_delta(p,c)['hitRatioPct'])
    def test_server_restart(self):
        self.assertIsNone(cache_delta({'pagesRequested':5,'pagesRead':1,'uptime':100},
            {'pagesRequested':500,'pagesRead':3,'uptime':1})['hitRatioPct'])
    def test_url_rejects_active_content(self):
        self.assertIsNone(safe_url('javascript:alert(1)'));self.assertIsNone(safe_url('https://u:p@host/a'))
    def test_parse_annual_dedup(self):
        line='- [Example](https://example.com) - [Security Report](Annual%20Security%20Reports/2025/Report.pdf) (2025) - Summary'
        rows=parse_annual('# Intro\n'+line+'\n'+line)
        self.assertEqual(len(rows),1);self.assertIn('/blob/main/Annual%20Security',rows[0]['url'])
    def test_feed(self):
        rss='<rss><channel><item><title>Phishing warning</title><link>https://example.com/a</link><description>&lt;b&gt;Read this&lt;/b&gt;</description></item></channel></rss>'
        x=parse_feed(rss,'https://example.com/feed')[0];self.assertEqual(x['summary'],'Read this')
    def test_bson_exact_size_all_id_ranges(self):
        for i in (0,9,999,99999):
            x=make_workload_doc(i,{'_id':'a'*24,'sourceId':'b'*24,'title':'é漢字'*50,'year':2025})
            self.assertEqual(len(BSON.encode(x)),2048)
if __name__=='__main__':unittest.main()
