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

class GeminiTests(unittest.TestCase):
 def test_config_requires_gemini_key_without_openai_fallback(self):
  with patch.dict(os.environ,{'LLM_BACKEND':'gemini','OPENAI_API_KEY':'unused'},clear=True):
   with self.assertRaisesRegex(chat.ChatError,'GEMINI_API_KEY'):chat.config()
 def test_defaults_and_provider_isolation(self):
  with patch.dict(os.environ,{'LLM_BACKEND':'gemini','GEMINI_API_KEY':'test'},clear=True):
   c=chat.config();self.assertEqual(c['dimensions'],3072);self.assertEqual(c['model'],'gemini-2.5-flash-lite');self.assertTrue(c['space'].startswith('gemini:'))
 def test_google_endpoint_and_key(self):
  import io
  with patch.dict(os.environ,{'GEMINI_API_KEY':'test-gemini','OPENAI_API_KEY':'must-not-use'}), patch.object(chat.urllib.request,'urlopen',return_value=io.BytesIO(b'{"ok":true}')) as request:
   self.assertEqual(chat.remote('/embeddings',{}, {'provider':'gemini'}),{'ok':True})
   req=request.call_args.args[0];self.assertEqual(req.full_url,'https://generativelanguage.googleapis.com/v1beta/openai/embeddings');self.assertEqual(req.get_header('Authorization'),'Bearer test-gemini')
 def test_embedding_and_stream_protocol(self):
  import io
  c={'provider':'gemini','embedding':'gemini-embedding-001','dimensions':2,'model':'gemini-2.5-flash-lite'}
  with patch.object(chat,'remote',return_value={'data':[{'index':0,'embedding':[3,4]}]}):self.assertEqual(chat.embed(['text'],c),[[.6,.8]])
  with patch.object(chat,'remote',return_value={'candidates':[{'content':{'parts':[{'text':'Cited [1]'}]}}]}) as request:
   self.assertEqual(list(chat.model_stream([],c)),[{'token':'Cited [1]'},{'usage':{'prompt_tokens':0,'completion_tokens':0}}]);self.assertEqual(request.call_args.args[1]['generationConfig']['thinkingConfig']['thinkingBudget'],0)
 def test_quota_error_has_no_secret_or_paid_fallback(self):
  import io,urllib.error
  error=urllib.error.HTTPError('https://example.invalid',429,'quota',{},io.BytesIO(b'{"error":{"message":"private-key"}}'))
  with patch.dict(os.environ,{'GEMINI_API_KEY':'test'}), patch.object(chat.urllib.request,'urlopen',side_effect=error):
   with self.assertRaises(chat.ChatError) as raised:chat.remote('/embeddings',{}, {'provider':'gemini'})
   self.assertIn('no paid fallback',str(raised.exception));self.assertNotIn('private-key',str(raised.exception))

class GeminiMissingIndexTests(unittest.TestCase):
 def test_omitted_zero_index(self):
  c={'provider':'gemini','embedding':'gemini-embedding-001','dimensions':2}
  with patch.object(chat,'remote',return_value={'data':[{'embedding':[3,4]}]}):
   self.assertEqual(chat.embed(['source'],c),[[.6,.8]])
 def test_omitted_zero_and_out_of_order_batch(self):
  c={'provider':'gemini','embedding':'gemini-embedding-001','dimensions':2}
  with patch.object(chat,'remote',return_value={'data':[{'index':1,'embedding':[0,1]},{'embedding':[1,0]}]}):
   self.assertEqual(chat.embed(['a','b'],c),[[1,0],[0,1]])
 def test_ambiguous_batch_rejected(self):
  c={'provider':'gemini','embedding':'gemini-embedding-001','dimensions':2}
  with patch.object(chat,'remote',return_value={'data':[{'embedding':[0,1]},{'embedding':[1,0]}]}):
   with self.assertRaisesRegex(chat.ChatError,'ambiguous'):chat.embed(['a','b'],c)

class GeminiAnswerTests(unittest.TestCase):
 def test_complete_answer_and_usage(self):
  c={'provider':'gemini','model':'gemini-2.5-flash-lite'}
  with patch.object(chat,'remote',return_value={'candidates':[{'content':{'parts':[{'text':'Evidence [1]'}]}}],'usageMetadata':{'candidatesTokenCount':4}}) as call:
   self.assertEqual(list(chat.model_stream([],c)),[{'token':'Evidence [1]'},{'usage':{'prompt_tokens':0,'completion_tokens':4}}])
   self.assertEqual(call.call_args.args[0],'/models/gemini-2.5-flash-lite:generateContent')
 def test_empty_answer_is_not_success(self):
  with patch.object(chat,'remote',return_value={'choices':[]}):
   with self.assertRaisesRegex(chat.ChatError,'no answer'):list(chat.model_stream([],{'provider':'gemini','model':'gemini-2.5-flash-lite'}))

class GeminiNativeTransportTests(unittest.TestCase):
 def test_native_url_and_key_header(self):
  import io
  with patch.dict(os.environ,{'GEMINI_API_KEY':'test-native'}),patch.object(chat.urllib.request,'urlopen',return_value=io.BytesIO(b'{}')) as call:
   chat.remote('/models/gemini-2.5-flash-lite:generateContent',{}, {'provider':'gemini'})
   req=call.call_args.args[0]
   self.assertEqual(req.full_url,'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent')
   self.assertEqual(req.get_header('X-goog-api-key'),'test-native')
   self.assertIsNone(req.get_header('Authorization'))
 def test_system_and_history_mapping(self):
  messages=[{'role':'system','content':'Cite sources.'},{'role':'user','content':'First'},{'role':'assistant','content':'Previous'},{'role':'user','content':'Follow-up'}]
  with patch.object(chat,'remote',return_value={'candidates':[{'content':{'parts':[{'text':'Done'}]}}]}) as call:
   list(chat.model_stream(messages,{'provider':'gemini','model':'gemini-2.5-flash-lite'}))
   payload=call.call_args.args[1]
   self.assertEqual([m['role'] for m in payload['contents']],['user','model','user'])
   self.assertEqual(payload['systemInstruction']['parts'][0]['text'],'Cite sources.')
