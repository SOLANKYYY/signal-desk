import os
from pathlib import Path
from pymongo import MongoClient, ASCENDING, TEXT
ROOT=Path(__file__).resolve().parents[1]
DB_NAME=os.getenv('MONGODB_DB','signal_desk')
if DB_NAME in ('admin','local','config'): raise RuntimeError('Choose a dedicated lab database.')
client=MongoClient(os.getenv('MONGODB_URI','mongodb://127.0.0.1:27017'),serverSelectionTimeoutMS=5000)
db=client[DB_NAME]

def indexes():
    db.sources.create_index('url',unique=True)
    db.reports.create_index('url',unique=True)
    db.reports.create_index([('title',TEXT),('summary',TEXT)], name='report_text')
    db.reports.create_index([('assessment.verdict',ASCENDING),('ingestedAt',-1)])
    db.reports.create_index([('assessment.category',ASCENDING),('ingestedAt',-1)])
    db.reports.create_index('sourceId')
    db.indicators.create_index([('type',ASCENDING),('value',ASCENDING)],unique=True)
    db.observations.create_index([('reportId',ASCENDING),('indicatorId',ASCENDING)],unique=True)
    db.observations.create_index('indicatorId')
    db.cache_samples.create_index('at',expireAfterSeconds=604800)
    db.cache_samples.create_index([('at',-1)])

    db.reports.create_index("entities")
    db.reports.create_index("publishedAt")
    db.evidence_passages.create_index([("reportId",1),("page",1)])

    db.reports.create_index([('triage.alert',1),('triage.rank',-1)])
    db.reports.create_index('processing.status')
