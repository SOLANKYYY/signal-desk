"""Feed-backed research API. Observables are claims, never automatic block decisions."""
import gzip, hashlib, ipaddress, json, os, re, urllib.request, urllib.error, uuid
from datetime import datetime, timezone
from pathlib import Path
from .db import db
from .core import now
from tools.threat_feed import FEEDS, fetch, event_url, normalize_event

def ensure_indexes():
    db.threat_events.create_index([('timestamp',-1),('_id',1)])
    db.threat_records.create_index([('source',1),('timestamp',-1)])
    db.threat_records.create_index('indicator')
    db.threat_records.create_index('event_id')
    db.intel_cases.create_index([('updatedAt',-1)])

def store_event(payload,feed):
    e=payload.get('Event',payload); eid=str(uuid.UUID(e['uuid'])); rows=normalize_event(payload,feed)
    stamp=datetime.fromtimestamp(int(e['timestamp']),timezone.utc)
    db.threat_events.update_one({'_id':eid},{'$set':{'title':str(e.get('info',''))[:500],
        'source':str(e.get('Orgc',{}).get('name') or feed),'feed':feed,'timestamp':stamp,
        'eventDate':e.get('date'),'url':event_url(feed,eid),'indicatorCount':len(rows),
        'status':'feed-reported','synthetic':False}},upsert=True)
    from pymongo import UpdateOne
    for start in range(0,len(rows),500):
        db.threat_records.bulk_write([UpdateOne({'_id':r['id']},{'$set':r},upsert=True) for r in rows[start:start+500]],ordered=False)
    return len(rows)

def seed_snapshot():
    """Explicit sync job only. Retry-safe upserts; never replaces live records."""
    marker='public-threat-snapshot-v1'
    if db.import_state.find_one({'_id':marker}):return
    from pymongo import UpdateOne
    file=Path(__file__).resolve().parents[1]/'data/public-threat-snapshot.json.gz'
    with gzip.open(file,'rt',encoding='utf-8') as f:data=json.load(f)
    for event in data['events']:
        event['timestamp']=datetime.fromisoformat(event['timestamp'])
        db.threat_events.update_one({'_id':event['_id']},{'$setOnInsert':event},upsert=True)
    for start in range(0,len(data['records']),500):
        db.threat_records.bulk_write([UpdateOne({'_id':r['id']},{'$setOnInsert':r},upsert=True)
          for r in data['records'][start:start+500]],ordered=False)
    db.import_state.update_one({'_id':marker},{'$set':{'at':now(),'provenance':data['provenance']}},upsert=True)

def sync_batch():
    ensure_indexes(); seed_snapshot(); checked=0; added=0; errors=[]
    for feed,base in FEEDS.items():
        try:
            manifest=fetch(base+'manifest.json'); feed_checked=0
            for eid,meta in sorted(manifest.items(),key=lambda x:int(x[1].get('timestamp',0)),reverse=True):
                url=event_url(feed,eid);state=db.import_state.find_one({'_id':'misp:'+feed+':'+eid}) or {}
                if state.get('upstreamTimestamp')==meta.get('timestamp'):continue
                try:
                    added+=store_event(fetch(url),feed)
                    db.import_state.update_one({'_id':'misp:'+feed+':'+eid},{'$set':{'at':now(),'upstreamTimestamp':meta.get('timestamp')}},upsert=True)
                    checked+=1; feed_checked+=1
                except Exception as exc:errors.append({'feed':feed,'event':eid,'error':type(exc).__name__});break
                if feed_checked>=2:break
        except Exception as exc:errors.append({'feed':feed,'error':type(exc).__name__})
        if checked>=4:break
    result={'events':checked,'observationsProcessed':added,'errors':errors,'at':now()}
    db.import_state.update_one({'_id':'misp-sync'},{'$set':result},upsert=True)
    return result

def query(args):
    q={};text=str(args.get('q','')).strip()[:160]
    if text:
        pattern=re.compile(re.escape(text),re.I)
        ids=db.threat_records.distinct('event_id',{'indicator':text})[:1000]
        q['$or']=[{'title':pattern},{'source':pattern},{'_id':{'$in':ids}}]
    if args.get('source'):q['source']=str(args['source'])[:200]
    return q

def summary():
    return {'events':db.threat_events.count_documents({}),'observations':db.threat_records.count_documents({}),
        'sources':len(db.threat_events.distinct('source')),'indexedReports':db.reports.count_documents({'pdf.status':'indexed'}),
        'lastSync':db.import_state.find_one({'_id':'misp-sync'}),
        'providers':[{'name':name,'url':url,'enabled':True} for name,url in FEEDS.items()],
        'virustotalConfigured':bool(os.getenv('VIRUSTOTAL_API_KEY')),
        'scope':'Published feed claims. Indicator observations are not confirmed incidents.'}

def events(args):
    page=max(1,min(10000,int(args.get('page',1))));q=query(args)
    return {'items':list(db.threat_events.find(q).sort([('timestamp',-1),('_id',1)]).skip((page-1)*20).limit(20)),
        'total':db.threat_events.count_documents(q),'page':page,'pageSize':20}

def event_detail(eid):
    eid=str(uuid.UUID(eid));event=db.threat_events.find_one({'_id':eid})
    if not event:raise ValueError('Event not found')
    event['indicators']=list(db.threat_records.find({'event_id':eid},{'_id':0}).limit(200))
    return event

def sources():
    return list(db.threat_events.aggregate([{'$group':{'_id':'$source','events':{'$sum':1},'lastSeen':{'$max':'$timestamp'}}},{'$sort':{'events':-1}}]))

def top():
    return list(db.threat_records.aggregate([{'$group':{'_id':'$indicator','observations':{'$sum':1},'lastModified':{'$max':'$timestamp'}}},{'$sort':{'observations':-1,'_id':1}},{'$limit':30}]))

def exports(args):
    limit=max(1,min(15000,int(args.get('limit',15000))))
    filt={}
    if args.get('source'):filt['source']=str(args['source'])[:200]
    rows=list(db.threat_records.find(filt,{'_id':0}).sort([('timestamp',-1),('_id',1)]).limit(limit))
    return {'records':rows,'exportedAt':now(),'count':len(rows),'record_unit':'MISP indicator attribute',
        'target_basis':'observable, not victim','timestamp_basis':'attribute modification time',
        'source_name':'Signal Desk public MISP feeds','next':None}

def check_message(text):
    if not isinstance(text,str) or len(text)>15000:raise ValueError('Message limit: 15,000 characters')
    links=sorted(set(re.findall(r'https?://[^\s<>"\x27]+',text)))[:50]
    cues=[label for pattern,label in [(r'urgent|immediately|expire','Urgency language'),(r'password|otp|verification code','Credential or code request'),(r'payment|wallet|bank','Financial language')] if re.search(pattern,text,re.I)]
    matches=list(db.threat_records.find({'indicator':{'$in':links}},{'_id':0}).limit(50))
    return {'links':links,'cues':cues,'feedMatches':matches,'verdict':'Review required; absence of a feed match does not establish safety.','externalRequests':False}

def vt_lookup(value):
    value=str(value).strip()
    # Hash lookup only: no files, URLs or private content submitted to a provider.
    if not re.fullmatch(r'(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})',value):raise ValueError('Enter an MD5, SHA1 or SHA256 hash')
    token=os.getenv('VIRUSTOTAL_API_KEY','')
    if not token:return {'available':False,'reason':'Set VIRUSTOTAL_API_KEY on the server to enable hash reputation lookup.'}
    req=urllib.request.Request('https://www.virustotal.com/api/v3/files/'+value.lower(),headers={'x-apikey':token})
    try:
        with urllib.request.urlopen(req,timeout=15) as r:data=json.load(r)
    except urllib.error.HTTPError as e:
        return {'available':False,'reason':'Hash not found' if e.code==404 else 'Provider returned HTTP '+str(e.code)}
    a=data['data']['attributes']
    return {'available':True,'sha256':a.get('sha256'),'stats':a.get('last_analysis_stats'),'analysisTime':a.get('last_analysis_date'),'source':'VirusTotal','note':'Provider results may be stale. No detection does not mean safe.'}

def save_case(body):
    title=str(body.get('title','')).strip()[:160];note=str(body.get('note','')).strip()[:10000]
    if not title:raise ValueError('Case title required')
    status=body.get('status','open')
    if status not in ('open','investigating','closed'):raise ValueError('Invalid case status')
    ident=str(uuid.UUID(body['id'])) if body.get('id') else str(uuid.uuid4())
    db.intel_cases.update_one({'_id':ident},{'$set':{'title':title,'note':note,'status':status,'updatedAt':now()},'$setOnInsert':{'createdAt':now()}},upsert=True)
    return db.intel_cases.find_one({'_id':ident})

def get(path,args):
    if path=='summary':return summary()
    if path=='events':return events(args)
    if path.startswith('event/'):return event_detail(path.split('/')[-1])
    if path=='sources':return sources()
    if path=='top':return top()
    if path=='export':return exports(args)
    if path=='cases':return list(db.intel_cases.find().sort('updatedAt',-1).limit(100))
    raise ValueError('Unknown intelligence route')

def post(path,body):
    if path=='message':return check_message(body.get('text',''))
    if path=='hash':return vt_lookup(body.get('hash',''))
    if path=='cases':return save_case(body)
    raise ValueError('Unknown intelligence action')
