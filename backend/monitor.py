"""Independent 10-second sampler plus background report discovery."""
import json, os, threading, time
from .db import db, ROOT
from .core import now, cache_delta
from .labs import raw_cache
from .ingest import sync_all

class Monitor:
    def __init__(self):
        self.stop_event=threading.Event();self.previous=None;self.latest=None
        self.sync_lock=threading.Lock();self.last_sync=None
        self.sync_seconds=max(10,int(os.getenv('SYNC_INTERVAL_SECONDS','300')))
        self.threads=[]
    def sample_once(self):
        try:
            current=raw_cache();sample=cache_delta(self.previous,current);self.previous=current
            self.latest=dict(sample,available=True)
            record=dict(self.latest,at=now())
            db.cache_samples.insert_one(record)
            folder=ROOT/'results';folder.mkdir(exist_ok=True)
            with (folder/'cache_monitor.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(self.latest,default=str)+'\n')
        except Exception as exc:self.latest={'available':False,'at':now().isoformat(),'error':str(exc), 'hitRatioPct':None}
        return self.latest
    def sync_once(self):
        if not self.sync_lock.acquire(blocking=False):return {'status':'already-running'}
        try:
            self.last_sync={'at':now().isoformat(),'results':sync_all()};return self.last_sync
        finally:self.sync_lock.release()
    def _samples(self):
        deadline=time.monotonic()
        while not self.stop_event.is_set():
            sample=self.sample_once();print(json.dumps({'monitor':sample},default=str),flush=True)
            deadline+=10
            self.stop_event.wait(max(0,deadline-time.monotonic()))
    def _syncs(self):
        while not self.stop_event.is_set():
            try:self.sync_once()
            except Exception as exc:self.last_sync={'at':now().isoformat(),'error':str(exc)}
            self.stop_event.wait(self.sync_seconds)
    def start(self):
        for target in (self._samples,self._syncs):
            thread=threading.Thread(target=target,daemon=True);thread.start();self.threads.append(thread)
    def stop(self):self.stop_event.set()

def run():
    monitor=Monitor();monitor.start()
    print('Cache every 10 seconds. New-report polling defaults to 300 seconds after each completed attempt. Ctrl+C stops.')
    try:
        while True:time.sleep(1)
    except KeyboardInterrupt:monitor.stop()
