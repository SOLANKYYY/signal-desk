"""Password-protected WSGI adapter for Vercel; local server remains unchanged."""
import hmac, io, json, os
from urllib.parse import urlparse
from flask import Flask, request, Response
from .db import db, ROOT, client
from .server import Handler, encode
from . import cloud

app=Flask(__name__,static_folder=None)
app.config['MAX_CONTENT_LENGTH']=10000

def respond(data,status=200):
    return Response(json.dumps(data,default=encode),status=status,mimetype='application/json',headers={'Cache-Control':'no-store'})

@app.before_request
def authorize():
    if request.path=='/api/cron':
        secret=os.getenv('CRON_SECRET','')
        if len(secret)>=32 and hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+secret):return
        return respond({'error':'Unauthorized cron request'},401)
    password=os.getenv('APP_PASSWORD','');username=os.getenv('APP_USERNAME','admin')
    if len(password)<16:return respond({'error':'Set APP_PASSWORD to at least 16 characters in Vercel, then redeploy.'},503)
    auth=request.authorization
    if not auth or auth.type!='basic' or not hmac.compare_digest((auth.username or '').encode(),username.encode()) or not hmac.compare_digest((auth.password or '').encode(),password.encode()):
        return Response('Sign in to Signal Desk.',401,headers={'WWW-Authenticate':'Basic realm="Signal Desk", charset="UTF-8"','Cache-Control':'no-store'})
    if request.method=='POST':
        origin=request.headers.get('Origin')
        if origin and urlparse(origin).netloc!=request.host:return respond({'error':'Cross-origin write blocked'},403)

class Bridge(Handler):
    def __init__(self):
        self.path=request.full_path.rstrip('?');self.headers=request.headers
        self.rfile=io.BytesIO(request.get_data());self.response=None
    def send_json(self,value,status=200):self.response=respond(value,status)

@app.route('/',methods=['GET'])
@app.route('/<path:path>',methods=['GET','POST'])
def route(path=''):
    if request.method=='GET' and path in ('','app.js','styles.css'):
        name=path or 'index.html';mime='text/html' if not path else 'application/javascript' if path.endswith('.js') else 'text/css'
        return Response((ROOT/'frontend'/name).read_bytes(),mimetype=mime,headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'",'X-Content-Type-Options':'nosniff'})
    if not path.startswith('api/'):return respond({'error':'Not found'},404)
    if not os.getenv('MONGODB_URI','').startswith(('mongodb://','mongodb+srv://')):return respond({'error':'Set the hosted MONGODB_URI environment variable and redeploy.'},503)
    try:
        cloud.bootstrap()
        if path=='api/health':
            client.admin.command('ping')
            return respond({'ok':True,'database':db.name,'cloud':True})
        if path=='api/processing':
            if request.method=='POST':
                body=request.get_json(silent=True)
                if not isinstance(body,dict):return respond({'error':'JSON object required'},400)
                return respond(cloud.control(body.get('action')))
            cloud.kick_auto()
            return respond(cloud.status())
        if path=='api/cron':
            result,status=cloud.enqueue_job('sync',{});return respond(result,status)
        if path=='api/jobs' and request.method=='GET':return respond(cloud.list_jobs())
        if path.startswith('api/jobs/') and request.method=='POST':
            body=request.get_json(silent=True)
            if not isinstance(body,dict):return respond({'error':'JSON object required'},400)
            result,status=cloud.enqueue_job(path.split('/')[-1],body);return respond(result,status)
        if path=='api/results':return respond({r['_id']:r['value'] for r in db.lab_results.find()})
        if path=='api/metrics':return respond({'latest':{'available':False,'hitRatioPct':None,'occupancyPct':None,'reason':'Continuous WiredTiger monitoring runs in the local version. Hosted database tiers may restrict these counters.'},'history':[]})
        if path=='api/capacity':return respond({'error':'Cache experiments run in the local version with your own MongoDB instance.'},400)
        if path=='api/source-status':return respond({'lastSync':db.import_state.find_one({'_id':'last-sync'}),'cloud':True,'syncSeconds':86400})
        bridge=Bridge()
        if request.method=='POST':bridge.do_POST()
        else:bridge.do_GET()
        # Keep internal DB/connection details out of public error responses.
        if bridge.response and bridge.response.status_code>=500:return respond({'error':'Backend operation failed. Check database access and Vercel logs.'},503)
        return bridge.response or respond({'error':'Not found'},404)
    except (ValueError,TypeError) as exc:return respond({'error':str(exc)},400)
    except Exception:
        app.logger.exception('Signal Desk cloud operation failed')
        return respond({'error':'Cloud backend unavailable. Check database connectivity and Vercel logs.'},503)
