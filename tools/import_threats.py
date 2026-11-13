"""Run from repo root: python -m tools.import_threats data/live-threats"""
import argparse,json
from pathlib import Path
from backend.intelligence import store_event,ensure_indexes
from tools.threat_feed import FEEDS

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    ensure_indexes();events=0
    for file in (a.directory/'feed-cache').glob('*.json'):
        payload=json.loads(file.read_text(encoding='utf-8'));event=payload.get('Event',payload)
        if 'uuid' not in event:continue
        # Locate provider from exported rows instead of guessing mirror identity.
        if events==0:
            providers={r['event_id']:r['feed'] for r in map(json.loads,(a.directory/'threats.jsonl').read_text(encoding='utf-8').splitlines())}
        feed=providers.get(event['uuid'])
        if feed in FEEDS:store_event(payload,feed);events+=1
    print(f'Imported {events} public source events; existing report reviews preserved.')
if __name__=='__main__':main()
