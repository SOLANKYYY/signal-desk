"""Local intelligence server: Python HTTP API + static browser frontend."""
import json, os, re, threading, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from bson import ObjectId
from datetime import datetime, timezone
from .db import db, client, ROOT, indexes
from .core import VERDICTS, CATEGORIES, now
from .ingest import seed
from .alerts import processor, alert_list, LEVELS, analyze_report
from .investigation import (search_query, entity_profiles, related_profile, index_pdf, evidence_search,
                            migrate_entities, labels, entities_for)
from .labs import size_analysis, redesign, generate_workload, random_reads, cache_capacity, save
from .monitor import Monitor
monitor=Monitor();jobs={};job_lock=threading.Lock()

def encode(value):
    if isinstance(value,datetime):return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    if isinstance(value,ObjectId):return str(value)
    raise TypeError(type(value).__name__)

def start_job(name, body=None):
    body=body or {}
    actions={'generate':generate_workload,'reads':random_reads,'sizes':size_analysis,
             'redesign':redesign,'sync':monitor.sync_once,'index-pdf':lambda:index_pdf(str(body.get('reportId','')))}
    if name not in actions:raise ValueError('Unknown job')
    with job_lock:
        if any(j['status']=='running' for j in jobs.values()):return {'error':'A job is already running'},409
        jobs[name]={'name':name,'status':'running','startedAt':now()}
    def work():
        try:
            result=actions[name]()
            with job_lock:jobs[name].update(status='completed',result=result,finishedAt=now())
        except Exception as exc:
            with job_lock:jobs[name].update(status='failed',error=str(exc),finishedAt=now())
    threading.Thread(target=work,daemon=True).start()
    return jobs[name],202

class Handler(BaseHTTPRequestHandler):
    def send_json(self,value,status=200):
        data=json.dumps(value,default=encode).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        try:self.get()
        except ValueError as e:self.send_json({'error':str(e)},400)
        except Exception as e:self.send_json({'error':str(e)},503)
    def get(self):
        u=urlparse(self.path);q={k:v[0] for k,v in parse_qs(u.query).items()};path=u.path
        if path=='/api/health':
            client.admin.command('ping');return self.send_json({'ok':True,'database':db.name})
        if path=='/api/summary':
            return self.send_json({'reports':db.reports.count_documents({}),'sources':db.sources.count_documents({}),
              'indicators':db.indicators.count_documents({}),'workload':db.working_set.count_documents({}),
              'verdicts':list(db.reports.aggregate([{'$group':{'_id':'$assessment.verdict','count':{'$sum':1}}}])),
              'categories':list(db.reports.aggregate([{'$group':{'_id':'$assessment.category','count':{'$sum':1}}}])),
              'lastSync':monitor.last_sync or db.import_state.find_one({'_id':'last-sync'}),
              'indexedReports':db.reports.count_documents({'pdf.status':'indexed'})})
        if path=='/api/reports':
            query=search_query(q.get('q',''))
            for parameter,field,allowed in [('verdict','assessment.verdict',VERDICTS),('category','assessment.category',CATEGORIES)]:
                value=q.get(parameter,'')
                if value:
                    if value not in allowed:raise ValueError('Invalid '+parameter)
                    query[field]=value
            if q.get('kind') in ('article','annual-report'):query['kind']=q['kind']
            if q.get('source'):query['sourceId']=q['source']
            if q.get('level'):
                if q['level'] not in LEVELS:raise ValueError('Invalid threat level')
                if q['level']=='not-assessed':
                    query.setdefault('$and',[]).append({'$or':[{'triage.level':'not-assessed'},{'triage.level':{'$exists':False}}]})
                else:query['triage.level']=q['level']
            for param, operator in [('from','$gte'),('to','$lte')]:
                if q.get(param):
                    date=datetime.strptime(q[param],'%Y-%m-%d').replace(tzinfo=timezone.utc)
                    if param=='to':date=date.replace(hour=23,minute=59,second=59,microsecond=999999)
                    query.setdefault('publishedAt',{})[operator]=date
            if q.get('from') and q.get('to') and q['from']>q['to']:raise ValueError('Start date must be before end date')
            if q.get('year'):
                year=int(q['year'])
                if not 2000<=year<=2100:raise ValueError('Choose a valid report year')
                query['year']=year
            sort={'newest':{'ingestedAt':-1,'_id':1},'oldest':{'ingestedAt':1,'_id':1},'title':{'title':1,'_id':1},'year':{'year':-1,'_id':1}}.get(q.get('sort','newest'))
            if not sort:raise ValueError('Invalid sort order')
            page=max(1,min(100000,int(q.get('page',1))));limit=15
            pipeline=[{'$match':query},{'$sort':sort},{'$skip':(page-1)*limit},{'$limit':limit},
                      {'$lookup':{'from':'sources','localField':'sourceId','foreignField':'_id','as':'source'}}]
            return self.send_json({'items':list(db.reports.aggregate(pipeline)),'total':db.reports.count_documents(query),'page':page,'pageSize':limit})
        if path.startswith('/api/reports/'):
            report=db.reports.find_one({'_id':path.split('/')[-1]})
            if not report:return self.send_json({'error':'Report not found'},404)
            report['source']=db.sources.find_one({'_id':report['sourceId']})
            report['observations']=list(db.observations.aggregate([{'$match':{'reportId':report['_id']}},
              {'$lookup':{'from':'indicators','localField':'indicatorId','foreignField':'_id','as':'indicator'}}]))
            report['evidence']=list(db.evidence_passages.find({'reportId':report['_id']},{'_id':0}).sort('page',1).limit(8))
            return self.send_json(report)
        if path=='/api/processing':return self.send_json(processor.status())
        if path=='/api/alerts':return self.send_json(alert_list(q.get('level',''),max(1,int(q.get('page',1))),q.get('ack')=='1'))
        if path=='/api/entities':return self.send_json(entity_profiles())
        if path=='/api/entity':return self.send_json(related_profile(q.get('name','')))
        if path=='/api/evidence':return self.send_json(evidence_search(q.get('q',''),max(1,min(100000,int(q.get('page','1'))))))
        if path=='/api/catalog':
            return self.send_json(list(db.reports.find({'kind':'annual-report'},{'title':1,'year':1,'pdf':1}).sort([('year',-1),('title',1)]).limit(3000)))
        if path=='/api/source-status':
            return self.send_json({'lastSync':monitor.last_sync or db.import_state.find_one({'_id':'last-sync'}),
                'syncSeconds':monitor.sync_seconds,'sources':['CTI Digest / configured RSS feeds','Annual security report repository']})
        if path=='/api/sources':return self.send_json(list(db.sources.find().sort('name',1)))
        if path=='/api/indicators':return self.send_json(list(db.indicators.find().limit(200)))
        if path=='/api/metrics':
            history=list(db.cache_samples.find({}, {'_id':0}).sort('at',-1).limit(60));history.reverse()
            return self.send_json({'latest':monitor.latest,'history':history})
        if path=='/api/capacity':
            result=cache_capacity();save('cache_capacity.json',result);return self.send_json(result)
        if path=='/api/jobs':
            with job_lock:result=list(jobs.values())
            return self.send_json(result)
        if path=='/api/results':
            result={}
            for name in ('schema_sizes.json','schema_redesign.json','workload_generation.json','workload_random_reads.json','cache_capacity.json'):
                file=ROOT/'results'/name
                if file.exists():result[name]=json.loads(file.read_text())
            return self.send_json(result)
        files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css'}
        if path not in files:return self.send_json({'error':'Not found'},404)
        file=ROOT/'frontend'/files[path];data=file.read_bytes()
        mime={'.html':'text/html','.js':'text/javascript','.css':'text/css'}[file.suffix]
        self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
    def do_POST(self):
        try:
            # Local analyst app; reject browser cross-origin writes. Do not expose publicly.
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):
                return self.send_json({'error':'Cross-origin write blocked'},403)
            length=int(self.headers.get('Content-Length','0'))
            if not 0<=length<=10000:raise ValueError('Request too large')
            body=json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body,dict):raise ValueError('JSON object required')
            path=urlparse(self.path).path
            if path=='/api/processing':return self.send_json(processor.control(body.get('action')))
            if path.startswith('/api/alerts/'):
                status=body.get('status')
                if status not in ('open','acknowledged'):raise ValueError('Invalid alert status')
                result=db.reports.update_one({'_id':path.split('/')[-1],'triage.alert':True},{'$set':{'alertStatus':status,'alertHandledAt':now()}})
                return self.send_json({'updated':result.matched_count},200 if result.matched_count else 404)
            if path.startswith('/api/jobs/'):
                result,status=start_job(path.split('/')[-1],body);return self.send_json(result,status)
            if path.startswith('/api/review/'):
                verdict=body.get('verdict');note=body.get('note','');category=body.get('category')
                if verdict not in VERDICTS or category not in CATEGORIES:raise ValueError('Invalid verdict or category')
                if not isinstance(note,str) or not 10<=len(note.strip())<=2000:raise ValueError('Evidence note must contain 10–2,000 characters')
                rid=path.split('/')[-1];report=db.reports.find_one({'_id':rid})
                if not report:return self.send_json({'error':'Report not found'},404)
                names=body.get('entities',report.get('analystEntities',[]))
                if not isinstance(names,list) or len(names)>20 or any(not isinstance(x,str) or len(x)>100 for x in names):
                    raise ValueError('Use at most 20 entity labels, each no longer than 100 characters')
                names=labels(names)
                entities=entities_for(report['title']+' '+report.get('summary',''),names+report.get('pdfEntities',[]))
                result=db.reports.update_one({'_id':rid},{'$set':{
                    'analystEntities':names,'entities':entities,
                    'assessment.verdict':verdict,'assessment.category':category,'assessment.note':note.strip(),
                    'assessment.reviewedAt':now(),'assessment.reviewedBy':'local-analyst'},
                    '$push':{'reviewHistory':{'$each':[{'at':now(),'previous':report['assessment'],
                        'verdict':verdict,'category':category,'note':note.strip()}],'$slice':-20}}})
                return self.send_json({'updated':result.matched_count},200 if result.matched_count else 404)
            return self.send_json({'error':'Not found'},404)
        except (ValueError,TypeError) as e:self.send_json({'error':str(e)},400)
        except Exception as e:self.send_json({'error':str(e)},503)

def main():
    client.admin.command('ping');indexes();print(seed());migrate_entities()
    if os.getenv('AUTO_MONITOR','1')=='1':monitor.start()
    processor.start()
    server=ThreadingHTTPServer(('127.0.0.1',int(os.getenv('PORT','8000'))),Handler)
    print('Open http://localhost:'+str(server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:processor.stop();monitor.stop();server.server_close();client.close()
if __name__=='__main__':main()
