import os,unittest
from unittest.mock import patch
from itsdangerous import TimestampSigner
from backend import web
class LoginTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'APP_PASSWORD':'test-password-long-enough','APP_USERNAME':'admin','VERCEL':'1'});self.env.start();self.addCleanup(self.env.stop)
  self.api=web.app.test_client()
 def sign_in(self,remember='yes'):
  return self.api.post('/login',data={'username':'admin','password':'test-password-long-enough','remember':remember},headers={'Origin':'https://localhost'})
 def test_no_browser_popup_and_login_page_available(self):
  r=self.api.get('/');self.assertEqual(r.status_code,303);self.assertEqual(r.headers['Location'],'/login');self.assertNotIn('WWW-Authenticate',r.headers)
  self.assertEqual(self.api.get('/login').status_code,200)
  self.assertEqual(self.api.get('/api/coursework').status_code,401)
 def test_persistent_cookie_attributes_and_access(self):
  r=self.sign_in();self.assertEqual(r.status_code,303)
  cookie=r.headers['Set-Cookie']
  for value in ('Max-Age=604800','Secure','HttpOnly','SameSite=Lax'):self.assertIn(value,cookie)
  self.assertEqual(self.api.get('/').status_code,200)
 def test_session_only_choice(self):self.assertNotIn('Max-Age',self.sign_in('').headers['Set-Cookie'])
 def test_wrong_password_does_not_set_cookie(self):
  r=self.api.post('/login',data={'username':'admin','password':'wrong'});self.assertNotIn('Set-Cookie',r.headers);self.assertIn('error=1',r.headers['Location'])
 def test_cross_origin_login_and_logout_rejected(self):
  for path in ('/login','/logout'):
   self.assertEqual(self.api.post(path,headers={'Origin':'https://evil.invalid'}).status_code,403)
 def test_signout_clears_browser_session(self):
  self.sign_in();self.assertEqual(self.api.post('/logout').status_code,303);self.assertEqual(self.api.get('/').status_code,303)
 def test_tampered_and_expired_tokens_rejected(self):
  self.api.set_cookie(web.COOKIE,'tampered');self.assertEqual(self.api.get('/').status_code,303)
  with patch.object(TimestampSigner,'get_timestamp',return_value=1):token=web.signer().dumps({'user':'admin'})
  self.api.set_cookie(web.COOKIE,token);self.assertEqual(self.api.get('/').status_code,303)
 def test_password_rotation_invalidates_cookie(self):
  self.sign_in()
  with patch.dict(os.environ,{'APP_PASSWORD':'replacement-password-long-enough'}):self.assertEqual(self.api.get('/').status_code,303)
