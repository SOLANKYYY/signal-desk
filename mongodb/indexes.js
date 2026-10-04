// Optional: mongosh mongodb://127.0.0.1:27017/signal_desk mongodb/indexes.js
// These mirror indexes the application automatically creates.
db.sources.createIndex({url: 1}, {unique: true});
db.reports.createIndex({url: 1}, {unique: true});
db.reports.createIndex({title: "text", summary: "text"}, {name: "report_text"});
db.reports.createIndex({"assessment.verdict": 1, ingestedAt: -1});
db.reports.createIndex({"assessment.category": 1, ingestedAt: -1});
db.reports.createIndex({sourceId: 1});
db.indicators.createIndex({type: 1, value: 1}, {unique: true});
db.observations.createIndex({reportId: 1, indicatorId: 1}, {unique: true});
db.observations.createIndex({indicatorId: 1});
db.cache_samples.createIndex({at: 1}, {expireAfterSeconds: 604800});
db.cache_samples.createIndex({at: -1});

db.reports.createIndex({entities: 1});
db.reports.createIndex({publishedAt: 1});
db.evidence_passages.createIndex({reportId: 1, page: 1});

db.reports.createIndex({'triage.alert': 1, 'triage.rank': -1});
db.reports.createIndex({'processing.status': 1});
