"""Docker FastAPI host, sharing Signal Desk's authenticated UI and chat engine."""
import os, hmac
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.middleware.wsgi import WSGIMiddleware
from .db import client, db
from . import chat
from .web import app as site

@asynccontextmanager
async def lifespan(app):
    client.admin.command('ping');chat.indexes(db)
    from .intelligence import seed_snapshot, ensure_indexes
    ensure_indexes();seed_snapshot()
    try:yield
    finally:client.close()

app=FastAPI(title='Signal Desk · Appendix A',lifespan=lifespan)

@app.middleware('http')
async def api_bounds(request,call_next):
    if request.method=='POST' and request.url.path in ('/chat','/ingest'):
        from urllib.parse import urlparse
        origin=request.headers.get('origin')
        if origin and urlparse(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'error':'Cross-origin write blocked'},status_code=403)
        limit=1024*1024 if request.url.path=='/ingest' else 10000
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>limit:return JSONResponse({'error':'Request too large'},status_code=413)
        request._body=bytes(data)
    return await call_next(request)

def owner(request):
    # API clients use the existing Basic credentials; no WWW-Authenticate popup.
    import base64
    password=os.getenv('APP_PASSWORD','');username=os.getenv('APP_USERNAME','admin')
    if len(password)<16:raise HTTPException(503,'Configure APP_PASSWORD (16+ characters).')
    try:
        scheme,value=request.headers.get('authorization','').split(' ',1)
        user,pwd=base64.b64decode(value,validate=True).decode().split(':',1)
        valid=scheme.lower()=='basic' and hmac.compare_digest(user.encode(),username.encode()) and hmac.compare_digest(pwd.encode(),password.encode())
    except Exception:valid=False
    if not valid:raise HTTPException(401,'Sign in with the configured application credentials.')
    return username

@app.get('/health')
def health():
    try:client.admin.command('ping');return {'status':'ok','database':'connected'}
    except Exception:raise HTTPException(503,'Database unavailable')

@app.post('/chat')
def ask(request:Request,body:dict):
    name=owner(request)
    import json
    return StreamingResponse((json.dumps(x,default=str)+'\n' for x in chat.chat_stream(db,name,body)),media_type='application/x-ndjson')

@app.post('/ingest')
def ingest(request:Request,body:dict):
    name=owner(request)
    try:return chat.ingest(db,name,body)
    except chat.ChatError as exc:raise HTTPException(exc.status,str(exc))

app.mount('/',WSGIMiddleware(site))
