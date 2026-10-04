"""Explainable report triage and a resumable, sequential catalog processor."""
import os, re, threading
from .core import now
from .db import db

LEVELS=('critical','high','medium','low','not-assessed')
VERSION='report-triage-v1'
# These are report-attention rules, not CVSS scores or proof of local compromise.
RULES=[
 ('critical','Reported active exploitation',r'\b(?:actively exploited|exploited in the wild|ongoing exploitation)\b'),
 ('high','Reported ransomware or destructive activity',r'\b(?:ransomware attack|ransomware campaign|data exfiltration|destructive malware|credential theft)\b'),
 ('medium','Threat or vulnerability discussed',r'\b(?:CVE-\d{4}-\d{4,}|ransomware|malware|phishing|vulnerability|vulnerabilities|botnet)\b')]
RANK={'critical':4,'high':3,'medium':2,'low':1,'not-assessed':0}

def evaluate(report,passages):
    base={'version':VERSION,'assessedAt':now(),'level':'not-assessed','rank':0,'alert':False,
          'basis':[],'method':'Transparent text rules; provisional report-attention level',
          'scope':'Report content only; not a live incident, local exposure assessment, or CVSS score.'}
    if report.get('provenance',{}).get('synthetic'):
        return dict(base,reason='Fictional scenario excluded from automatic alerts.')
    if not passages:
        summary=report.get('summary','')
        if report.get('kind')=='annual-report' or len(summary.strip())<100:
            return dict(base,reason='Insufficient source text. Download and extraction required; metadata alone is not rated.')
        passages=[{'text':summary,'page':None}]
    hits=[]
    for level,reason,pattern in RULES:
        compiled=re.compile(pattern,re.I)
        for passage in passages:
            for sentence in re.split(r'(?<=[.!?])\s+|\n+',passage.get('text','')):
                if not compiled.search(sentence):continue
                # Common negation/illustration cues are excluded. This is still heuristic.
                if re.search(r'\b(?:not|never|no evidence|no known|hypothetical|fictional|simulation)\b',sentence,re.I):continue
                match=compiled.search(sentence);start=max(0,match.start()-90)
                hits.append({'level':level,'reason':reason,'page':passage.get('page'),
                             'excerpt':sentence[start:start+320]})
                break
            if len([x for x in hits if x['level']==level])>=2:break
    top=max(hits,key=lambda x:RANK[x['level']]) if hits else None
    level=top['level'] if top else 'low'
    return dict(base,level=level,rank=RANK[level],alert=level in ('critical','high'),basis=hits[:6],
                reason=top['reason'] if top else 'No configured higher-priority threat cues found in extracted text. This does not establish safety.',
                textCoverage=report.get('pdf',{}),historicalYear=report.get('year'),
                context='Publication context may be historical; verify dates, affected products and relevance.')

def analyze_report(report_id):
    report=db.reports.find_one({'_id':report_id})
    if not report:return None
    passages=list(db.evidence_passages.find({'reportId':report_id},{'text':1,'page':1}).sort('page',1))
    result=evaluate(report,passages)
    db.reports.update_one({'_id':report_id},{'$set':{'triage':result}})
    return result

def alert_list(level='',page=1,include_ack=False):
    query={'triage.alert':True,'provenance.synthetic':{'$ne':True}}
    if level:
        if level not in LEVELS:raise ValueError('Invalid threat level')
        query['triage.level']=level
    if not include_ack:query['alertStatus']={'$ne':'acknowledged'}
    return {'items':list(db.reports.find(query).sort([('triage.rank',-1),('triage.assessedAt',-1),('_id',1)]).skip((page-1)*15).limit(15)),
            'total':db.reports.count_documents(query),'page':page,'pageSize':15,
            'levels':list(db.reports.aggregate([{'$match':{'provenance.synthetic':{'$ne':True}}},
                {'$group':{'_id':'$triage.level','count':{'$sum':1}}}]))}

class Processor:
    def __init__(self):
        self.stop_event=threading.Event();self.wake=threading.Event();self.current=None;self.last_error=None;self.thread=None
    def enabled(self):
        state=db.import_state.find_one({'_id':'auto-process'}) or {}
        return state.get('enabled',os.getenv('AUTO_PROCESS_REPORTS','1')=='1')
    def control(self,action):
        if action not in ('start','pause','retry'):raise ValueError('Unknown processing action')
        if action=='retry':
            db.reports.update_many({'processing.status':'failed'},{'$unset':{'processing':1}})
        db.import_state.update_one({'_id':'auto-process'},{'$set':{'enabled':action!='pause','updatedAt':now()}},upsert=True)
        self.wake.set();return self.status()
    def status(self):
        total=db.reports.count_documents({'kind':'annual-report'})
        indexed=db.reports.count_documents({'kind':'annual-report','pdf.status':'indexed'})
        failed=db.reports.count_documents({'kind':'annual-report','processing.status':'failed','pdf.status':{'$ne':'indexed'}})
        errors=list(db.reports.find({'processing.status':'failed'},{'title':1,'processing':1}).limit(10))
        return {'enabled':self.enabled(),'current':self.current,'total':total,'indexed':indexed,'failed':failed,
                'remaining':max(0,total-indexed-failed),'errors':errors,'lastError':self.last_error,
                'note':'Sequential PDF download → text extraction → automatic triage. Pause takes effect after the current report. Failed reports require Retry failed.'}
    def process_one(self):
        from .investigation import index_pdf
        # New articles and existing evidence are rated without waiting for all downloads.
        for report in db.reports.find({'triage.version':{'$ne':VERSION}}).limit(50):analyze_report(report['_id'])
        report=db.reports.find_one({'kind':'annual-report','pdf.status':{'$ne':'indexed'},'processing.status':{'$ne':'failed'}},sort=[('year',-1),('_id',1)])
        if not report:return False
        rid=report['_id'];self.current={'id':rid,'title':report['title']}
        db.reports.update_one({'_id':rid},{'$set':{'processing':{'status':'running','at':now()}}})
        try:
            index_pdf(rid);analyze_report(rid)
            db.reports.update_one({'_id':rid},{'$set':{'processing':{'status':'completed','at':now()}}})
        except Exception as exc:
            db.reports.update_one({'_id':rid},{'$set':{'processing':{'status':'failed','at':now(),'error':str(exc)[:500]}}})
        finally:self.current=None
        return True
    def run(self):
        while not self.stop_event.is_set():
            delay=15
            try:
                if self.enabled():delay=2 if self.process_one() else 30
                self.last_error=None
            except Exception as exc:self.last_error=str(exc)[:500]
            self.wake.wait(delay);self.wake.clear()
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def stop(self):self.stop_event.set();self.wake.set()

processor=Processor()
