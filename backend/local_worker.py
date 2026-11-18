"""Single local worker: durable MongoDB queue with restart recovery."""
import time
from datetime import timedelta
from pymongo import ReturnDocument
from .cloud import db, work, now

def main():
    while True:
        job=db.local_queue.find_one_and_update(
            {'$or':[{'status':'pending'},{'status':'running','leaseUntil':{'$lt':now()}}],'attempts':{'$lt':3}},
            {'$set':{'status':'running','leaseUntil':now()+timedelta(hours=1)},'$inc':{'attempts':1}},
            return_document=ReturnDocument.AFTER)
        if not job:
            time.sleep(2);continue
        try:
            work(job['payload'])
            db.local_queue.update_one({'_id':job['_id']},{'$set':{'status':'completed','finishedAt':now()}})
        except Exception:
            db.local_queue.update_one({'_id':job['_id']},{'$set':{'status':'pending' if job['attempts']<3 else 'failed','error':'Task failed; inspect application job status.'}})
            time.sleep(5)

if __name__=='__main__':main()
