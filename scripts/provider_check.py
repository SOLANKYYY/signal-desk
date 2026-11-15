"""Opt-in deployment diagnostics: fixed public prompt, no secrets or bodies logged."""
import json,os,re,urllib.request,urllib.error

def check(label,url,headers,payload=None):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers=headers,data=None if payload is None else json.dumps(payload).encode()),timeout=25) as r:d=json.load(r)
  if label=='gemini_models':
   names=[m.get('name','') for m in d.get('models',[]) if 'generateContent' in m.get('supportedGenerationMethods',[])]
   print('MODEL_CHECK',label,json.dumps([n for n in names if re.fullmatch(r'models/[a-zA-Z0-9._-]+',n)]))
  else:print('MODEL_CHECK',label,'ACCESSIBLE',any(m.get('id')==os.getenv('OPENAI_MODEL','gpt-4o-mini') for m in d.get('data',[])))
 except urllib.error.HTTPError as e:
  code='unknown'
  try:
   detail=json.loads(e.read(16000)).get('error',{});candidate=detail.get('type') or detail.get('status') or detail.get('code')
   if candidate in ('insufficient_quota','RESOURCE_EXHAUSTED','NOT_FOUND','INVALID_ARGUMENT','PERMISSION_DENIED','invalid_api_key'):code=candidate
  except Exception:pass
  print('MODEL_CHECK',label,'HTTP',e.code,code)
 except Exception as e:print('MODEL_CHECK',label,'CONNECTION',type(e).__name__)

def main():
 key=os.getenv('GEMINI_API_KEY')
 if key:
  check('gemini_models','https://generativelanguage.googleapis.com/v1beta/models?pageSize=100',{'x-goog-api-key':key})
 key=os.getenv('OPENAI_API_KEY')
 if key:check('openai_models','https://api.openai.com/v1/models',{'Authorization':'Bearer '+key})
if __name__=='__main__':main()
