import os,uuid,unittest,json
from unittest.mock import patch
import mongomock
from backend import chat,web

class ChatTests(unittest.TestCase):
 def setUp(self):
  self.db=mongomock.MongoClient().test
  self.env=patch.dict(os.environ,{'LLM_BACKEND':'openai','OPENAI_API_KEY':'test-only','EMBEDDING_DIMENSIONS':'2','CHAT_RETRIEVAL':'exact','APP_PASSWORD':'unit-test-long-password','APP_USERNAME':'admin','MONGODB_URI':'mongodb://unused'});self.env.start();self.addCleanup(self.env.stop)
  self.emb=patch.object(chat,'embed',side_effect=lambda texts,c:[[1.,0.] for _ in texts]);self.emb.start();self.addCleanup(self.emb.stop)
  self.sid=str(uuid.uuid4())
 def doc(self,**extra):return {'title':'Vendor advisory','text':'Evidence of a vulnerability affecting Windows. Review the vendor advisory for supported remediation.','url':'https://vendor.example/advisory','platform':'windows','stage':'active','assessment':'Analyst reviewed the advisory identifying current exploitation.',**extra}
 def seed(self):return chat.ingest(self.db,'admin',{'documents':[self.doc()]})
 def answer(self,owner='admin',**extra):
  body={'session_id':self.sid,'message':'What does the evidence show?',**extra}
  with patch.object(chat,'model_stream',return_value=iter([{'token':'Evidence [1].'},{'usage':{'completion_tokens':3}}])):return list(chat.chat_stream(self.db,owner,body))
 def test_multidoc_idempotence_and_update(self):
  docs=[self.doc(),self.doc(title='Second',url='https://vendor.example/second')]
  self.assertEqual(chat.ingest(self.db,'admin',{'documents':docs})['documents'],2)
  chat.ingest(self.db,'admin',{'documents':docs});self.assertEqual(self.db.chat_chunks.count_documents({}),2)
 def test_invalid_stage_needs_basis(self):
  with self.assertRaises(chat.ChatError):chat.ingest(self.db,'admin',{'documents':[self.doc(assessment='')]})
 def test_invalid_document_writes_nothing(self):
  with self.assertRaises(chat.ChatError):chat.ingest(self.db,'admin',{'documents':[self.doc(),self.doc(url='javascript:alert(1)')]})
  self.assertEqual(self.db.chat_chunks.count_documents({}),0)
 def test_filters_no_silent_broadening(self):
  self.seed();events=self.answer(platform='linux');self.assertEqual(events[-1]['type'],'error');self.assertEqual(self.db.chat_turns.count_documents({}),0)
 def test_stream_sources_and_persistence(self):
  self.seed();events=self.answer();self.assertEqual([e['type'] for e in events],['sources','token','done'])
  saved=chat.history(self.db,'admin',self.sid);self.assertEqual(saved[0]['answer'],'Evidence [1].');self.assertEqual(saved[0]['sources'][0]['url'],'https://vendor.example/advisory')
 def test_owner_isolation(self):
  self.seed();self.answer();self.assertEqual(chat.history(self.db,'other',self.sid),[])
 def test_followup_last_five_exchanges(self):
  self.seed()
  for i in range(7):self.answer()
  with patch.object(chat,'model_stream',return_value=iter([{'token':'Followup [1]'}])) as model:
   list(chat.chat_stream(self.db,'admin',{'session_id':self.sid,'message':'Follow up'}));messages=model.call_args.args[0]
   self.assertEqual(len(messages),12);self.assertEqual(messages[0]['role'],'system')
 def test_failed_generation_not_saved(self):
  self.seed()
  with patch.object(chat,'model_stream',side_effect=chat.ChatError('Unavailable',503)):
   events=list(chat.chat_stream(self.db,'admin',{'session_id':self.sid,'message':'Help'}))
  self.assertEqual(events[-1]['type'],'error');self.assertEqual(self.db.chat_turns.count_documents({}),0);self.assertFalse(self.db.chat_metrics.find_one()['ok'])
 def test_rate_limit(self):
  for i in range(12):chat.limit(self.db,'admin','chat',12)
  with self.assertRaises(chat.ChatError) as e:chat.limit(self.db,'admin','chat',12)
  self.assertEqual(e.exception.status,429)
 def test_provider_missing_is_explicit(self):
  with patch.dict(os.environ,{'LLM_BACKEND':''}):self.assertFalse(chat.status(self.db)['configured'])
 def test_feed_import_does_not_infer_status(self):
  self.db.threat_events.insert_one({'_id':'feed-event','title':'Windows advisory','url':'https://feed.example/event','timestamp':'2020-01-01'})
  chat.import_feed(self.db,'admin',{'event_ids':['feed-event']});d=self.db.chat_chunks.find_one();self.assertEqual(d['stage'],'unassessed');self.assertEqual(d['platform'],'unknown')
 def test_exact_limit(self):
  self.db.chat_chunks.insert_many([{'space':chat.config()['space'],'embedding':[1,0]} for i in range(3001)])
  with self.assertRaises(chat.ChatError):chat.retrieve(self.db,'q','all','all',chat.config())
 def test_bad_uuid_and_input(self):
  self.assertEqual(self.answer(session_id='wrong')[-1]['type'],'error')
  self.assertEqual(self.answer(message={'$ne':None})[-1]['type'],'error')
 def test_http_auth_and_stream(self):
  with patch.object(web,'db',self.db):
   client=web.app.test_client();self.assertEqual(client.get('/api/assistant/status').status_code,401)
   client.post('/login',data={'username':'admin','password':'unit-test-long-password'})
   self.assertEqual(client.get('/api/assistant/status').status_code,200)
   self.assertEqual(client.post('/api/assistant/ingest',json={'documents':[self.doc()]},headers={'Origin':'https://evil.invalid'}).status_code,403)
   self.seed()
   with patch.object(chat,'model_stream',return_value=iter([{'token':'Answer [1]'}])):
    r=client.post('/api/assistant/chat',json={'session_id':self.sid,'message':'Explain'})
    self.assertEqual(r.status_code,200);self.assertIn('application/x-ndjson',r.content_type);self.assertEqual(json.loads(r.data.decode().splitlines()[-1])['type'],'done')
 def test_atlas_pipeline_filters(self):
  self.seed();c={**chat.config(),'retrieval':'atlas'}
  with patch.object(self.db.chat_chunks,'aggregate',return_value=[]) as agg:
   chat.retrieve(self.db,'question','windows','active',c)
   spec=agg.call_args.args[0][0]['$vectorSearch'];self.assertEqual(spec['filter']['platform'],'windows');self.assertEqual(spec['filter']['stage'],'active')
 def test_untrusted_source_has_no_tools(self):
  self.seed()
  with patch.object(chat,'model_stream',return_value=iter([{'token':'[1]'}])) as m:
   list(chat.chat_stream(self.db,'admin',{'session_id':self.sid,'message':'Explain'}));messages=m.call_args.args[0]
   self.assertIn('untrusted',messages[0]['content']);self.assertIn('untrusted_evidence',messages[-1]['content'])

class EmbeddingTests(unittest.TestCase):
 def test_real_embedding_normalization_and_dimension_validation(self):
  c={'provider':'ollama','embedding':'nomic','dimensions':2}
  with patch.object(chat,'remote',return_value={'embeddings':[[3,4]]}):self.assertEqual(chat.embed(['x'],c),[[.6,.8]])
  with patch.object(chat,'remote',return_value={'embeddings':[[3,4,5]]}):
   with self.assertRaises(chat.ChatError):chat.embed(['x'],c)

class ProviderErrorTests(unittest.TestCase):
 def error(self,status,code):
  import io,urllib.error
  response=io.BytesIO(json.dumps({'error':{'code':code,'message':'secret-provider-text'}}).encode())
  return urllib.error.HTTPError('https://api.openai.com/v1/embeddings',status,'Rejected',{},response)
 def test_provider_errors_are_specific_and_do_not_leak_bodies(self):
  for status,code,expected in [(429,'insufficient_quota','quota'),(401,'invalid_api_key','rejected the API key'),(403,'permission_denied','permissions'),(429,'rate_limit_exceeded','rate limit'),(404,'model_not_found','model was not found')]:
   with self.subTest(status=status,code=code),patch.dict(os.environ,{'OPENAI_API_KEY':'not-a-real-key'}),patch('urllib.request.urlopen',side_effect=self.error(status,code)):
    with self.assertRaises(chat.ChatError) as error:chat.remote('/embeddings',{}, {'provider':'openai'})
    self.assertIn(expected,str(error.exception));self.assertNotIn('secret-provider-text',str(error.exception))
