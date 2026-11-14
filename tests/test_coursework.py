import unittest
from unittest.mock import patch
import mongomock
from pymongo.errors import ConnectionFailure
from backend import coursework as c

class CourseworkTests(unittest.TestCase):
 def setUp(self):self.db=mongomock.MongoClient().test
 def payload(self,n=11):return {'experiment':n,'documents':[{'filename':'evidence.json','data':{'experiment':n,'passed':True,'checks':{'counts':True}}}]}
 def test_distinct_repositories_and_reported_status(self):
  rows=c.catalog(self.db)['items'];self.assertEqual(len(rows),8)
  self.assertEqual(len({r['dockerUrl'] for r in rows}),8)
  self.assertTrue(all(r['evidence'] is None and not r['publicationVerified'] for r in rows))
  self.assertTrue(rows[2]['dockerUrl'].endswith('/mongodb-exercise13'))
 def test_import_persists_and_replaces_only_selected_experiment(self):
  c.import_evidence(self.db,self.payload());c.import_evidence(self.db,self.payload(12));c.import_evidence(self.db,self.payload())
  self.assertEqual(self.db.coursework_evidence.count_documents({}),2)
  row=c.catalog(self.db)['items'][0];self.assertEqual(row['status'],'Imported: reports pass')
  self.assertNotIn('data',row['evidence']['documents'][0])
  self.assertTrue(c.export_evidence(self.db,11)['documents'][0]['data']['passed'])
 def test_failed_file_is_not_all_pass(self):
  p=self.payload();p['documents'].append({'filename':'backup.json','data':{'passed':False}})
  c.import_evidence(self.db,p);self.assertEqual(c.catalog(self.db)['items'][0]['status'],'Evidence imported')
 def test_mismatch_rejected(self):
  p=self.payload();p['documents'][0]['data']['experiment']=12
  with self.assertRaises(ValueError):c.import_evidence(self.db,p)
 def test_credentials_and_private_keys_rejected(self):
  for value in [{'password':'secret'},{'nested':[{'api_key':'secret'}]},{'text':'-----BEGIN PRIVATE KEY-----'},{'uri':'mongodb://user:pass@host/db'}]:
   p=self.payload();p['documents'][0]['data']=value
   with self.assertRaises(ValueError):c.import_evidence(self.db,p)
  self.assertEqual(self.db.coursework_evidence.count_documents({}),0)
 def test_empty_duplicate_and_oversized_rejected(self):
  for docs in [[],[{'filename':'x.json','data':{}}],self.payload()['documents']*2,[{'filename':'big.json','data':{'text':'x'*960000}}]]:
   with self.assertRaises(ValueError):c.import_evidence(self.db,{'experiment':11,'documents':docs})
 def test_non_boolean_pass_not_trusted(self):
  p=self.payload();p['documents'][0]['data']['passed']='true';c.import_evidence(self.db,p)
  self.assertEqual(c.catalog(self.db)['items'][0]['status'],'Evidence imported')
 def test_database_outage_keeps_catalogue(self):
  with patch.object(self.db.coursework_evidence,'find',side_effect=ConnectionFailure('down')):
   result=c.catalog(self.db);self.assertEqual(len(result['items']),8);self.assertFalse(result['storageAvailable'])
