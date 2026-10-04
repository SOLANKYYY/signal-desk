"""Public metadata import. Never download or execute threat artifacts."""
import json, os, urllib.request, urllib.error, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime
from datetime import timezone
from .core import *
from .db import db, ROOT, indexes
MAX_DOWNLOAD=8*1024*1024

def fetch(url, etag=None):
    headers={'User-Agent':'SignalDesk/1.0 (educational metadata collector)'}
    if etag: headers['If-None-Match']=etag
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=15) as r:
            content=r.read(MAX_DOWNLOAD+1)
            if len(content)>MAX_DOWNLOAD: raise ValueError('Source exceeds 8 MiB ingestion limit')
            return content.decode('utf-8',errors='replace'),r.headers.get('ETag')
    except urllib.error.HTTPError as e:
        if e.code==304: return None,etag
        raise

def ingest_rows(rows):
    inserted=0
    for row in rows:
        url=safe_url(row.get('url',''))
        if not url: continue
        publisher_reference=safe_url(row.get('publisherUrl','')) or row['origin']
        publisher_parts=urlsplit(publisher_reference)
        source_url=publisher_parts.scheme+'://'+publisher_parts.netloc
        sid=key(source_url)
        db.sources.update_one({'_id':sid},{'$setOnInsert':{'name':row['publisher'][:200],
            'url':source_url,'createdAt':now(),'role':'publisher-not-threat-actor'}},upsert=True)
        report={'_id':key(url),'url':url,'title':row['title'][:500],
                'summary':row.get('summary','')[:2500], 'sourceId':sid,
                'kind':row.get('kind','article'), 'year':row.get('year'),
                'publishedAt':row.get('publishedAt'), 'ingestedAt':now(),
                'provenance':{'origin':row['origin'],'publisherReferenceUrl':publisher_reference,
                              'synthetic':row.get('synthetic',False)},
                'assessment':classify(row['title'],row.get('summary',''))}
        from .investigation import report_entities
        report['entities']=report_entities(report)
        result=db.reports.update_one({'_id':report['_id']},{'$setOnInsert':report},upsert=True)
        inserted+=int(result.upserted_id is not None)
    return inserted

class DigestParser(HTMLParser):
    def __init__(self):
        super().__init__();self.feeds=[];self.articles=[];self.depth=0;self.link=None;self.text=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='link' and a.get('type','') in ('application/rss+xml','application/atom+xml'):
            if u:=safe_url(a.get('href',''),CTI_URL): self.feeds.append(u)
        if tag=='article': self.depth+=1
        if tag=='a' and self.depth:
            self.link=safe_url(a.get('href',''),CTI_URL);self.text=[]
    def handle_data(self,data):
        if self.link:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.link:
            title=clean(' '.join(self.text))
            if len(title)>15:self.articles.append({'title':title,'url':self.link})
            self.link=None
        if tag=='article':self.depth=max(0,self.depth-1)

def parse_feed(xml,feed_url):
    root=ET.fromstring(xml)
    rows=[]
    def text(node,name):
        return next((''.join(x.itertext()) for x in node if x.tag.split('}')[-1]==name),'')
    for item in root.iter():
        if item.tag.split('}')[-1] not in ('item','entry'):continue
        link=text(item,'link')
        if not link:
            link=next((x.attrib.get('href','') for x in item if x.tag.split('}')[-1]=='link' and x.attrib.get('rel','alternate')=='alternate'),'')
        url=safe_url(link,feed_url);title=clean(text(item,'title'))
        if not url or not title:continue
        date_text=text(item,'pubDate') or text(item,'published') or text(item,'updated')
        try: date=parsedate_to_datetime(date_text)
        except (ValueError,TypeError):
            try: date=datetime.fromisoformat(date_text.replace('Z','+00:00'))
            except (ValueError,TypeError): date=None
        if date and not date.tzinfo:date=date.replace(tzinfo=timezone.utc)
        rows.append({'title':title,'url':url,'publisher':urlsplit(url).hostname,
          'publisherUrl':urlsplit(url).scheme+'://'+urlsplit(url).netloc,
          'summary':clean(text(item,'description') or text(item,'summary'))[:2500],
          'publishedAt':date,'origin':feed_url,'kind':'article'})
    return rows

def sync_annual():
    state=db.import_state.find_one({'_id':'annual'}) or {}
    content,etag=fetch(README_URL,state.get('etag'))
    if content is None:return {'source':'annual','inserted':0,'status':'not-modified'}
    rows=parse_annual(content)
    if not rows:raise ValueError('No annual-report entries found; upstream format may have changed.')
    inserted=ingest_rows(rows)
    db.import_state.update_one({'_id':'annual'},{'$set':{'etag':etag,'checkedAt':now(),'entries':len(rows)}},upsert=True)
    return {'source':'annual','inserted':inserted,'parsed':len(rows),'status':'ok'}

def sync_digest():
    rows=[];warnings=[];feeds=[]
    try:
        html_text,_=fetch(CTI_URL);parser=DigestParser();parser.feed(html_text)
        feeds=parser.feeds
        for item in parser.articles:
            host=urlsplit(item['url']).netloc
            rows.append(dict(item,publisher=host,publisherUrl='https://'+host,origin=CTI_URL))
    except Exception as exc:warnings.append('CTI Digest: '+str(exc))
    # Optional administrator-configured publisher RSS URLs, never user-supplied API URLs.
    feeds+= [u.strip() for u in os.getenv('CTI_FEED_URLS','').split(',') if u.strip()]
    for feed in dict.fromkeys(feeds):
        try:
            if not safe_url(feed) or not feed.startswith('https://'):raise ValueError('HTTPS feed URL required')
            body,_=fetch(feed);rows+=parse_feed(body,feed)
        except Exception as exc:warnings.append('Feed '+feed+': '+str(exc))
    if not rows:warnings.append('No public articles/feed found. The site may require JavaScript or block automated requests. Add a permitted RSS URL via CTI_FEED_URLS; no live data was fabricated.')
    return {'source':'ctidigest','inserted':ingest_rows(rows),'parsed':len(rows),'warnings':warnings,
            'status':'ok' if rows else 'unavailable'}

def sync_all():
    results=[]
    for func in (sync_annual,sync_digest):
        try:results.append(func())
        except Exception as exc:results.append({'source':func.__name__,'status':'error','error':str(exc)})
    db.import_state.update_one({'_id':'last-sync'},{'$set':{'at':now(),'results':results}},upsert=True)
    return results

def seed():
    indexes()
    rows=json.loads((ROOT/'data/annual_snapshot.json').read_text())
    n=ingest_rows(rows)
    demos=[('Ransomware scenario: encrypted workstation','ransomware','lab-c2.example.invalid'),
           ('Phishing scenario: lookalike login page','phishing','lab-login.example.invalid'),
           ('Vulnerability scenario: patch prioritization','vulnerability','lab-patch.example.invalid'),
           ('Malware scenario: suspicious executable hash','malware','lab-malware.example.invalid'),
           ('Security awareness scenario: benign newsletter','general','lab-news.example.invalid')]
    for i,(title,category,value) in enumerate(demos):
        url='https://example.invalid/training/'+str(i)
        n+=ingest_rows([{'title':title,'url':url,'publisher':'Fictional training feed',
              'publisherUrl':'https://example.invalid','origin':CTI_URL,'synthetic':True,
              'summary':'Fictional scenario for analyst review. This is not a real incident or live IOC.'}])
        iid=key(value)
        db.indicators.update_one({'_id':iid},{'$setOnInsert':{'type':'domain','value':value,'synthetic':True}},upsert=True)
        db.observations.update_one({'reportId':key(url),'indicatorId':iid},{'$setOnInsert':{
            'reportId':key(url),'indicatorId':iid,'context':'Fictional training example','firstSeen':now()}},upsert=True)
    return {'inserted':n,'reports':db.reports.count_documents({}),'note':'Snapshot metadata plus five explicitly fictional CTI scenarios.'}
