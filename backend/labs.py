"""Actual MongoDB measurements. No simulated cache telemetry."""
import argparse, json, random, statistics, time, os
from bson import BSON
from .db import db, client, ROOT, indexes
from .core import now, cache_sample, cache_delta
from .ingest import seed, sync_all
LIMIT=16*1024*1024
COLLECTIONS=('sources','reports','indicators','observations','evidence_passages','reports_embedded','working_set')

def save(name,value):
    if os.getenv('VERCEL')=='1':
        db.lab_results.replace_one({'_id':name},{'_id':name,'value':value},upsert=True)
        return name
    folder=ROOT/'results';folder.mkdir(exist_ok=True)
    path=folder/name;temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,default=str,indent=2),encoding='utf-8');temporary.replace(path);return path

def size_analysis():
    output=[]
    for name in COLLECTIONS:
        result=list(db[name].aggregate([{'$project':{'bytes':{'$bsonSize':'$$ROOT'}}},
          {'$group':{'_id':None,'count':{'$sum':1},'averageBytes':{'$avg':'$bytes'},
             'minBytes':{'$min':'$bytes'},'maxBytes':{'$max':'$bytes'},
             'totalBytes':{'$sum':'$bytes'},'approachingLimit':{'$sum':{'$cond':[{'$gte':['$bytes',int(LIMIT*0.8)]},1,0]}}}}]))
        entry=result[0] if result else {'count':0,'averageBytes':0,'minBytes':0,'maxBytes':0,'totalBytes':0,'approachingLimit':0}
        entry.pop('_id',None);entry.update(collection=name,limitBytes=LIMIT,
           maximumPctOfLimit=100*entry['maxBytes']/LIMIT,allBelowLimit=entry['maxBytes']<LIMIT)
        output.append(entry)
    data={'measuredAt':now(),'nearLimitThresholdPct':80,'collections':output}
    save('schema_sizes.json',data);return data

def redesign():
    """Materialize a disposable alternative, preserving canonical reports."""
    pipeline=[{'$lookup':{'from':'sources','localField':'sourceId','foreignField':'_id','as':'source'}},
              {'$unwind':'$source'},{'$unset':'sourceId'},{'$set':{'snapshotAt':now()}},
              {'$out':'reports_embedded'}]
    list(db.reports.aggregate(pipeline))
    source=db.reports.find_one({})
    if not source:raise ValueError('Run seed first')
    rid=source['_id']
    referenced=[{'$match':{'_id':rid}}, {'$lookup':{'from':'sources','localField':'sourceId','foreignField':'_id','as':'source'}}]
    embedded=[{'$match':{'_id':rid}}]
    result={'createdAt':now(),'count':db.reports_embedded.count_documents({}),
      'referencedExplain':db.command('explain',{'aggregate':'reports','pipeline':referenced,'cursor':{}},verbosity='executionStats'),
      'embeddedExplain':db.command('explain',{'aggregate':'reports_embedded','pipeline':embedded,'cursor':{}},verbosity='executionStats'),
      'interpretation':'Embedded report detail avoids a source lookup. Source corrections require updating every embedded copy; snapshot can become stale. Explain timings are observations, not guaranteed speedups.'}
    save('schema_redesign.json',result);return result

def make_workload_doc(i,report):
    doc={'_id':i,'reportId':report['_id'],'title':report['title'][:240],
         'sourceId':report['sourceId'],'year':report.get('year'),'synthetic':True,
         'purpose':'Working-set analysis generated workload; not a distinct report','padding':''}
    gap=2048-len(BSON.encode(doc))
    if gap<0:raise ValueError('Workload metadata too large')
    rng=random.Random(i)
    # Diverse ASCII padding reduces unrealistic compression of one repeated character.
    doc['padding']=''.join(rng.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',k=gap))
    assert len(BSON.encode(doc))==2048
    return doc

def generate_workload(count=100000):
    if count!=100000:raise ValueError('Generation requires exactly 100,000 documents')
    templates=list(db.reports.find({'kind':'annual-report'},{'title':1,'sourceId':1,'year':1}))
    if not templates:raise ValueError('Seed or import annual reports before generating the workload')
    # The only cleared collection is the explicitly disposable lab collection.
    db.working_set.drop()
    for start in range(0,count,1000):
        db.working_set.insert_many([make_workload_doc(i,templates[i%len(templates)]) for i in range(start,min(count,start+1000))])
    result={'generatedAt':now(),'count':db.working_set.count_documents({}),
            'bytesPerDocument':2048,'totalLogicalBytes':count*2048,'synthetic':True}
    save('workload_generation.json',result);return result

def raw_cache():
    # Cache counters do not need process-memory/extra-info sections.
    return cache_sample(client.admin.command({'serverStatus':1,'mem':0,'extra_info':0}))

def cache_capacity():
    sample=raw_cache()
    if sample['maximumBytes'] is None:raise RuntimeError('WiredTiger cache metrics not available on this server')
    stats=db.command('collStats','working_set')
    logical=stats.get('size',0);index=stats.get('totalIndexSize',0)
    return dict(sample,collectionCount=stats.get('count',0),logicalBytes=logical,
      onDiskBytes=stats.get('storageSize',0),indexBytesOnDisk=index,
      lowerOrderFootprintEstimateBytes=logical+index,
      footprintToCachePct=100*(logical+index)/sample['maximumBytes'],
      note='Occupancy is instance-wide. Logical data plus on-disk indexes is a rough planning estimate, not measured resident percentage of this collection.')

def random_reads(passes=3,limit=100000):
    if db.working_set.count_documents({})!=100000:raise ValueError('Generate the 100,000-document workload first')
    rng=random.Random(71);results=[]
    for p in range(passes):
        ids=list(range(100000));rng.shuffle(ids);ids=ids[:limit]
        previous=raw_cache();started=time.perf_counter();latencies=[];rows=0;payload=0
        for offset in range(0,len(ids),200):
            batch=ids[offset:offset+200];t=time.perf_counter()
            docs=list(db.working_set.find({'_id':{'$in':batch}}))
            latencies.append((time.perf_counter()-t)*1000);rows+=len(docs)
            payload+=sum(len(d['padding']) for d in docs) # Forces full-document reads, not a covered query.
        current=raw_cache();elapsed=time.perf_counter()-started
        results.append({'pass':p+1,'documentsRead':rows,'fullCollectionPass':len(ids)==100000,
          'seconds':elapsed,'documentsPerSecond':rows/elapsed,'batchSize':200,
          'medianBatchMs':statistics.median(latencies),'p95BatchMs':sorted(latencies)[int((len(latencies)-1)*.95)],
          'paddingBytesConsumed':payload,'cache':cache_delta(previous,current)})
        save('workload_random_reads.json',{'measuredAt':now(),'passes':results})
    return {'measuredAt':now(),'passes':results}

def main():
    parser=argparse.ArgumentParser(description='Signal Desk MongoDB tools')
    parser.add_argument('command',choices=['seed','sync','sizes','redesign','generate','capacity','reads','monitor'])
    parser.add_argument('--passes',type=int,default=3)
    parser.add_argument('--reads',type=int,default=100000,help='Reads per pass; default covers all 100,000 IDs in randomized order')
    args=parser.parse_args()
    try:
        client.admin.command('ping');indexes()
        if args.command=='monitor':
            from .monitor import run
            run();return
        if not 1<=args.passes<=20 or not 1<=args.reads<=100000:parser.error('Invalid passes/reads range')
        actions={'seed':seed,'sync':sync_all,'sizes':size_analysis,'redesign':redesign,
                 'generate':generate_workload,'capacity':cache_capacity,
                 'reads':lambda:random_reads(args.passes,args.reads)}
        result=actions[args.command]()
        if args.command=='capacity':save('cache_capacity.json',result)
        print(json.dumps(result,default=str,indent=2))
    finally:client.close()
if __name__=='__main__':main()
