"""Portable BSON dump for Schema analysis; BSON retains dates and ObjectIds."""
import argparse, hashlib, json
from bson import BSON, decode_file_iter
from .db import db, ROOT, indexes, client
COLLECTIONS=('sources','reports','indicators','observations','evidence_passages','import_state')
def export_dump():
    folder=ROOT/'data/dump';folder.mkdir(exist_ok=True);manifest={}
    for name in COLLECTIONS:
        path=folder/(name+'.bson');count=0
        with path.open('wb') as f:
            for doc in db[name].find():f.write(BSON.encode(doc));count+=1
        manifest[name]={'count':count,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest

def restore_dump():
    folder=ROOT/'data/dump';manifest=json.loads((folder/'manifest.json').read_text());result={}
    # Validate the entire input before applying writes. Restoring overwrites matching IDs.
    decoded={}
    for name in COLLECTIONS:
        if name not in manifest:continue  # Older four-collection snapshots remain supported.
        path=folder/(name+'.bson')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest[name]['sha256']:raise ValueError('Checksum failed: '+name)
        with path.open('rb') as f:decoded[name]=list(decode_file_iter(f))
        if len(decoded[name])!=manifest[name]['count']:raise ValueError('Count failed: '+name)
    for name,docs in decoded.items():
        for doc in docs:db[name].replace_one({'_id':doc['_id']},doc,upsert=True)
        result[name]=len(docs)
    indexes()
    from .investigation import migrate_entities
    migrate_entities();return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['export','restore']);args=p.parse_args()
    try:print(json.dumps(export_dump() if args.action=='export' else restore_dump(),indent=2))
    finally:client.close()
