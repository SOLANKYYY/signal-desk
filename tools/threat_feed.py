"""Public MISP JSON collector. No indicator URL is ever visited.
Export unit: one published indicator attribute, not one incident or victim.
"""
import argparse, hashlib, json, re, time, urllib.request, uuid
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

FEEDS = {'circl': 'https://www.circl.lu/doc/misp/feed-osint/',
         'botvrij': 'https://www.botvrij.eu/data/feed-osint/'}
TYPES = {'ip-src','ip-dst','domain','hostname','url','md5','sha1','sha256','sha512',
         'domain|ip','ip-src|port','ip-dst|port','filename|md5','filename|sha1','filename|sha256'}
LIMIT = 32 * 1024 * 1024

class FixedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlsplit
        if urlsplit(newurl).scheme != 'https' or urlsplit(newurl).hostname != urlsplit(req.full_url).hostname:
            raise ValueError('Feed redirected outside its HTTPS host')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(url, cache=None):
    if not any(url.startswith(base) for base in FEEDS.values()): raise ValueError('Unsupported feed URL')
    file = cache / (hashlib.sha256(url.encode()).hexdigest()+'.json') if cache else None
    if file and file.exists(): return json.loads(file.read_text(encoding='utf-8'))
    request=urllib.request.Request(url, headers={'User-Agent':'SignalDesk-EducationalCollector/2.0'})
    with urllib.request.build_opener(FixedRedirect()).open(request,timeout=30) as response:
        raw=response.read(LIMIT+1)
    if len(raw)>LIMIT: raise ValueError('Feed response exceeds 32 MiB')
    value=json.loads(raw)
    if file:
        cache.mkdir(parents=True,exist_ok=True); file.write_bytes(raw)
    return value

def event_url(feed, event_id):
    return FEEDS[feed]+str(uuid.UUID(event_id))+'.json'

def normalize_event(payload, feed):
    e=payload.get('Event',payload)
    eid=str(uuid.UUID(e['uuid'])); url=event_url(feed,eid)
    # MISP timestamp is the attribute modification time, not incident time.
    attributes=list(e.get('Attribute',[]))
    for obj in e.get('Object',[]): attributes.extend(obj.get('Attribute',[]))
    records=[]
    for a in attributes:
        if a.get('deleted') in (True,1,'1','true') or a.get('type') not in TYPES: continue
        value=str(a.get('value','')).strip()
        if not value or len(value)>4096: continue
        try:
            aid=str(uuid.UUID(a['uuid']))
            stamp=datetime.fromtimestamp(int(a['timestamp']),timezone.utc)
            if stamp>datetime.now(timezone.utc): continue
        except (KeyError,ValueError,TypeError,OverflowError,OSError): continue
        records.append({'id':aid,'source':str(e.get('Orgc',{}).get('name') or feed),
            'target':value,'type':a['type'],'timestamp':stamp.isoformat(),'indicator':value,
            'event_id':eid,'feed':feed,'event_url':url,'event_date':e.get('date'),
            'title':str(e.get('info',''))[:500], 'record_unit':'MISP indicator attribute',
            'timestamp_basis':'attribute modification time','target_basis':'reported observable, not victim',
            'to_ids':a.get('to_ids') is True})
    return records

def collect(output, desired=15000, max_events=2500):
    output.mkdir(parents=True,exist_ok=True); cache=output/'feed-cache'
    work=[]
    for feed,base in FEEDS.items():
        manifest=fetch(base+'manifest.json')
        ordered=sorted(manifest.items(),key=lambda pair:int(pair[1].get('timestamp',0)),reverse=True)
        work.append([(feed,event_url(feed,k)) for k,v in ordered])
    # Interleave feeds; exclude duplicate attribute UUIDs across mirrors.
    queue=[x for pair in __import__('itertools').zip_longest(*work) for x in pair if x][:max_events]
    records={}; errors=[]; fetched=0
    def get(item):
        feed,url=item
        try:return normalize_event(fetch(url,cache),feed),None
        except Exception as e:return [],{'url':url,'error':type(e).__name__+': '+str(e)}
    for start in range(0,len(queue),4):
        with ThreadPoolExecutor(max_workers=4) as pool:
            for rows,error in pool.map(get,queue[start:start+4]):
                fetched+=1
                if error: errors.append(error)
                for row in rows:
                    old=records.get(row['id'])
                    if old is None or row['timestamp']>old['timestamp']: records[row['id']]=row
        print(f'{fetched} events checked; {len(records):,} unique indicator observations; {len(errors)} fetch errors',flush=True)
        if len(records)>=desired and len({r['source'] for r in records.values()})>=2: break
        time.sleep(.1)
    rows=sorted(records.values(),key=lambda r:(r['timestamp'],r['id']),reverse=True)[:desired]
    target=output/'threats.jsonl'; temporary=output/'threats.jsonl.tmp'
    with temporary.open('w',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    temporary.replace(target)
    meta={'source_name':'Signal Desk / CIRCL and Botvrij public MISP feeds',
        'collected_at':datetime.now(timezone.utc).isoformat(),'record_unit':'MISP indicator attribute',
        'timestamp_basis':'attribute modification time, not observed attack time',
        'target_basis':'reported observable, not a victim or attack destination',
        'origin_attestation':'Fetched original public MISP JSON. Attributes are feed claims, not independently confirmed incidents. No synthetic padding.',
        'unique_records':len(rows),'distinct_events':len({r['event_id'] for r in rows}),
        'feeds':FEEDS,'events_checked':fetched,'errors':errors,
        'export_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'selection':'Newest attribute modification times within downloaded events; partial feed coverage.'}
    (output/'source.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({k:meta[k] for k in ('unique_records','distinct_events','record_unit')},indent=2))
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('data/live-threats'))
    p.add_argument('--count',type=int,default=15000);p.add_argument('--max-events',type=int,default=2500)
    a=p.parse_args()
    if a.count<1 or not 1<=a.max_events<=5000:p.error('Invalid count or event limit')
    meta=collect(a.output,a.count,a.max_events)
    if meta['unique_records']<a.count:raise SystemExit('Insufficient real records. Partial export saved; no records fabricated.')
