import os,unittest,uuid
from unittest.mock import patch
import mongomock
from backend import chat

class ChatUsabilityTests(unittest.TestCase):
    def setUp(self):
        self.db=mongomock.MongoClient().db
        self.env=patch.dict(os.environ,{'LLM_BACKEND':'ollama','EMBEDDING_DIMENSIONS':'2','EMBEDDING_MODEL':'test','CHAT_RETRIEVAL':'exact','OLLAMA_MODEL':'test'});self.env.start();self.addCleanup(self.env.stop)
    def test_empty_library_allows_labelled_general_guidance_and_saves(self):
        with patch.object(chat,'model_stream',return_value=iter([{'token':'General guidance: phishing is a deceptive message.'}])) as model:
            events=list(chat.chat_stream(self.db,'admin',{'session_id':str(uuid.uuid4()),'message':'What is phishing?'}))
        self.assertEqual(events[-1]['type'],'done');self.assertEqual(events[0]['sources'],[])
        self.assertIn('non-technical',model.call_args.args[0][0]['content']);self.assertEqual(self.db.chat_turns.count_documents({}),1)
    def test_website_is_saved_and_only_its_passages_retrieved(self):
        doc={'title':'Public guide','text':'A public guide explaining suspicious messages and verification.','url':'https://example.org/guide','platform':'unknown','stage':'unassessed'}
        with patch('backend.public_page.read_page',return_value=doc),patch.object(chat,'embed',side_effect=lambda texts,c:[[1.,0.] for t in texts]),patch.object(chat,'model_stream',return_value=iter([{'token':'Explanation [1].'}])):
            events=list(chat.chat_stream(self.db,'admin',{'session_id':str(uuid.uuid4()),'message':'Explain this','source_url':doc['url']}))
        self.assertEqual(events[-1]['type'],'done');self.assertEqual(events[0]['sources'][0]['url'],doc['url']);self.assertEqual(self.db.chat_chunks.count_documents({}),1)
    def test_website_failure_is_not_a_completed_answer(self):
        from backend.public_page import PageError
        with patch('backend.public_page.read_page',side_effect=PageError('Private address blocked')):
            events=list(chat.chat_stream(self.db,'admin',{'session_id':str(uuid.uuid4()),'message':'Read','source_url':'https://localhost/'}))
        self.assertEqual(events[-1]['type'],'error');self.assertEqual(self.db.chat_turns.count_documents({}),0)

if __name__=='__main__':unittest.main()
