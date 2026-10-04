"""Durable Vercel queue coordination. No detached threads or local results files."""
import os, uuid
from datetime import timedelta
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from .db import db, indexes
from .core import now
from .alerts import processor

TOPIC='signal-desk-tasks'

def publish(payload,key):
    from vercel.queue.sync import send
    from vercel.queue import DuplicateIdempotencyKeyError
    try:return send(TOPIC,payload,idempotency_key=key,retention=timedelta(days=7))
    except DuplicateIdempotencyKeyError:return None

def bootstrap():
    if db.import_state.find_one({'_id':'cloud-schema','version':1}):return
    from .ingest import seed
    from .investigation import migrate_entities
    owner=uuid.uuid4().hex
    if not acquire('bootstrap',owner):raise ValueError('Database setup is in progress. Refresh shortly.')
    try:
        if not db.import_state.find_one({'_id':'cloud-schema','version':1}):
            indexes();seed();migrate_entities()
            db.import_state.update_one({'_id':'cloud-schema'},{'$set':{'version':1,'at':now()}},upsert=True)
    finally:release('bootstrap',owner)

def acquire(name,owner,minutes=6):
    try:db.cloud_locks.update_one({'_id':name},{'$setOnInsert':{'until':now()}},upsert=True)
    except DuplicateKeyError:pass
    return db.cloud_locks.find_one_and_update({'_id':name,'until':{'$lte':now()}},
        {'$set':{'owner':owner,'until':now()+timedelta(minutes=minutes)}},return_document=ReturnDocument.AFTER) is not None

def release(name,owner):
    db.cloud_locks.update_one({'_id':name,'owner':owner},{'$set':{'until':now()}})

def kick_auto():
    if not processor.enabled():return
    if not db.reports.find_one({'$or':[{'kind':'annual-report','pdf.status':{'$ne':'indexed'},'processing.status':{'$ne':'failed'}},{'triage.version':{'$exists':False}}]},{'_id':1}):return
    owner=uuid.uuid4().hex
    if not acquire('kick-auto',owner):return
    try:
        state=db.import_state.find_one({'_id':'cloud-chain'}) or {}
        heartbeat=state.get('heartbeat')
        if heartbeat and heartbeat.tzinfo is None:heartbeat=heartbeat.replace(tzinfo=now().tzinfo)
        if state.get('active') and heartbeat and heartbeat>now()-timedelta(minutes=10):return
        token=uuid.uuid4().hex
        db.import_state.update_one({'_id':'cloud-chain'},{'$set':{'generation':token,'active':True,'heartbeat':now(),'error':None}},upsert=True)
        try:publish({'action':'auto','generation':token,'step':0},token+':0')
        except Exception:
            db.import_state.update_one({'_id':'cloud-chain','generation':token},{'$set':{'active':False,'error':'Queue could not be started. Check Vercel Queues configuration and retry Start / resume all.'}})
            raise ValueError('Could not start Vercel Queues. Check project queue availability and deployment logs.') from None
    finally:release('kick-auto',owner)

def control(action):
    result=processor.control(action)
    if action=='pause':db.import_state.update_one({'_id':'cloud-chain'},{'$set':{'active':False,'generation':uuid.uuid4().hex}},upsert=True)
    else:kick_auto()
    return status()

def status():
    result=processor.status();state=db.import_state.find_one({'_id':'cloud-chain'}) or {}
    current=db.reports.find_one({'processing.status':'running'},{'title':1})
    result.update(cloud=True,current={'id':current['_id'],'title':current['title']} if current else None,
                  lastError=state.get('error'),queueActive=state.get('active',False))
    return result

def list_jobs():
    # A killed serverless invocation cannot run its finally block.
    expired={'status':'running','expiresAt':{'$lte':now()}}
    for job in db.cloud_jobs.find(expired,{'_id':1}):
        result=db.cloud_jobs.update_one({'_id':job['_id'],**expired},{'$set':{
            'status':'failed','finishedAt':now(),
            'error':'Cloud job timed out or queue delivery was delayed. You can retry the job.'}})
        if result.modified_count:release('manual-job',job['_id'])
    return list(db.cloud_jobs.find().sort('startedAt',-1).limit(20))

def enqueue_job(name,body):
    if name not in ('sync','index-pdf','sizes','redesign'):
        raise ValueError('This database workload runs locally. Cloud supports sync, PDF indexing and schema analysis.')
    job_id=uuid.uuid4().hex
    list_jobs()
    if not acquire('manual-job',job_id,minutes=12):return {'error':'A cloud job is already queued or running. Wait for it to finish.'},409
    doc={'_id':job_id,'name':name,'body':body,'status':'running','startedAt':now(),'expiresAt':now()+timedelta(minutes=12)}
    db.cloud_jobs.insert_one(doc)
    try:publish({'action':'job','id':job_id},'job:'+job_id)
    except Exception:
        db.cloud_jobs.update_one({'_id':job_id},{'$set':{'status':'failed','error':'Could not publish cloud job. Check Vercel Queues configuration.','finishedAt':now()}})
        release('manual-job',job_id)
        raise ValueError('Could not publish cloud job. Check Vercel Queues configuration.') from None
    return doc,202

def work(message):
    action=message.get('action')
    if action=='auto':
        token=message['generation'];delivery=token+':'+str(message.get('step',0))
        if db.cloud_deliveries.find_one({'_id':delivery}):return
        state=db.import_state.find_one({'_id':'cloud-chain','generation':token})
        if not state or not processor.enabled():return
        db.import_state.update_one({'_id':'cloud-chain','generation':token},{'$set':{'heartbeat':now()}})
        processor.process_one()
        if processor.enabled() and db.import_state.find_one({'_id':'cloud-chain','generation':token}):
            remaining=db.reports.count_documents({'kind':'annual-report','pdf.status':{'$ne':'indexed'},'processing.status':{'$ne':'failed'}})
            unassessed=db.reports.count_documents({'triage.version':{'$exists':False}})
            if remaining or unassessed:
                step=message.get('step',0)+1
                publish({'action':'auto','generation':token,'step':step},token+':'+str(step))
            else:db.import_state.update_one({'_id':'cloud-chain','generation':token},{'$set':{'active':False}})
        db.import_state.update_one({'_id':'cloud-chain','generation':token},{'$set':{'heartbeat':now()}})
        db.cloud_deliveries.update_one({'_id':delivery},{'$set':{'at':now()}},upsert=True)
        return
    if action!='job':raise ValueError('Unsupported queue message')
    list_jobs()
    job_id=message['id'];job=db.cloud_jobs.find_one({'_id':job_id})
    if not job or job['status'] in ('completed','failed'):return
    deadline=now()+timedelta(minutes=6)
    db.cloud_jobs.update_one({'_id':job_id},{'$set':{'runningAt':now(),'expiresAt':deadline}})
    db.cloud_locks.update_one({'_id':'manual-job','owner':job_id},{'$set':{'until':deadline}})
    from .ingest import sync_all
    from .investigation import index_pdf
    from .labs import size_analysis,redesign
    actions={'sync':lambda:{'results':sync_all()},'index-pdf':lambda:index_pdf(str(job['body'].get('reportId',''))),
             'sizes':size_analysis,'redesign':redesign}
    try:
        result=actions[job['name']]()
        db.cloud_jobs.update_one({'_id':job_id},{'$set':{'status':'completed','result':result,'finishedAt':now()}})
        if job['name']=='sync':kick_auto()
    except Exception:
        db.cloud_jobs.update_one({'_id':job_id},{'$set':{'status':'failed','error':'Cloud job failed. Check deployment logs or the report download failure panel.','finishedAt':now()}})
        raise
    finally:release('manual-job',job_id)
