"""Course catalogue and authenticated, source-labelled student evidence imports."""
import hashlib,json,re
from datetime import datetime,timezone
from pymongo.errors import PyMongoError

TOPICS=[
 (11,'Sharding & horizontal scalability','Scale','Evaluate shard keys and compare timestamp hotspots with hashed distribution.',['Shard-key decision matrix','10,000 records per collection','Per-shard counts and explain routing']),
 (12,'Security & the CIA triad','Security','Demonstrate least privilege, salary redaction and encrypted MongoDB connections.',['Collection-scoped RBAC','Salary-redacted view','TLS and negative connection tests']),
 (13,'Containers & the cloud','Operations','Run a replica set in Docker and verify StatefulSet recovery in Kubernetes.',['Three-node replica set','Prometheus monitoring','Pod recreation and persistent data']),
 (14,'Production database services','Operations','Monitor MongoDB and verify that backups restore the original data.',['Monitoring and alerts','Backup/restore integrity','Measured RPO and RTO']),
 (15,'MongoDB-backed SaaS','Application','Build an isolated multi-tenant API and compare tenant migration strategies.',['JWT identity and RBAC','Atomic rate limiting','Tenant migration validation']),
 (16,'Cassandra & Neo4j','Multi-database','Model one dataset across three databases and combine their strengths.',['Equivalent enrollment queries','Hybrid fraud-query service','Connection pooling and circuit breaker']),
 (17,'Vector search & RAG','AI & retrieval','Retrieve relevant documents, build grounded answers and compare vector indexes.',['Chunking and retrieval','Conversation memory','Latency and recall measurements']),
 (18,'Comparative capstone','Multi-database','Compare a threat-intelligence workload across MongoDB, Cassandra and Neo4j.',['Four benchmark query patterns','False-positive analysis','Comparative report and scale discussion']),
]
REPOS={n:('mongodb-exercise13' if n==13 else 'nosql-exercise'+str(n)) for n,*_ in TOPICS}

def catalog(db):
 available=True
 try: saved={x['_id']:x for x in db.coursework_evidence.find({}, {'documents.data':0})}
 except PyMongoError:saved={};available=False
 items=[]
 for n,title,category,description,outcomes in TOPICS:
  item={'number':n,'title':title,'category':category,'description':description,'outcomes':outcomes,
        'dockerUrl':'https://hub.docker.com/r/solankyyy/'+REPOS[n],
        'referenceUrl':'https://github.com/sujeetjagtap/NoSQL-Databases-using-MongoDB/tree/main/chapter-'+str(n),
        'status':'Completion reported','statusBasis':'Student reports completion; run evidence has not yet been imported here.',
        'publicationVerified':False,'evidence':None}
  if n in saved:
   row=saved[n];item['evidence']={k:v for k,v in row.items() if k!='_id'}
   item['status']='Imported: reports pass' if row['allReportedPass'] else 'Evidence imported'
   item['statusBasis']='Imported JSON is a student-provided record, not an independent rerun.'
  items.append(item)
 return {'items':items,'storageAvailable':available,'basis':'Completion is student-reported until evidence is imported. Docker links are repository targets, not live registry verification.'}

def inspect(value,depth=0):
 if depth>35:raise ValueError('JSON nesting is too deep')
 if isinstance(value,dict):
  for k,v in value.items():
   if re.fullmatch(r'(password|pwd|token|api[_-]?key|secret|private[_-]?key|credentials|mongodb_uri)',k,re.I):raise ValueError('Remove credentials or secrets before importing evidence')
   inspect(v,depth+1)
 elif isinstance(value,list):
  for v in value:inspect(v,depth+1)
 elif isinstance(value,str):
  if 'PRIVATE KEY-----' in value or re.search(r'mongodb(?:\+srv)?://[^\s]+@',value) or re.search(r'dckr_pat_[A-Za-z0-9_-]+',value):raise ValueError('Secret material detected; do not import this file')

def import_evidence(db,body):
 n=body.get('experiment');docs=body.get('documents')
 if type(n) is not int or n not in REPOS:raise ValueError('Choose an experiment from 11 to 18')
 if not isinstance(docs,list) or not 1<=len(docs)<=15:raise ValueError('Select 1 to 15 result JSON files')
 encoded=json.dumps(body,allow_nan=False,separators=(',',':')).encode()
 if len(encoded)>950000:raise ValueError('Combined JSON must be smaller than 950 KB')
 clean=[]
 for doc in docs:
  if not isinstance(doc,dict):raise ValueError('Invalid result document')
  name=doc.get('filename');data=doc.get('data')
  if not isinstance(name,str) or not re.fullmatch(r'[\w .()-]{1,120}\.json',name):raise ValueError('Use a plain .json filename')
  if not isinstance(data,(dict,list)) or not data:raise ValueError('Each result must contain a JSON object or array')
  inspect(data)
  if isinstance(data,dict) and 'experiment' in data and str(data['experiment'])!=str(n):raise ValueError('The evidence experiment number does not match your selection')
  canonical=json.dumps(data,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
  clean.append({'filename':name,'sha256':hashlib.sha256(canonical).hexdigest(),'reportedPass':isinstance(data,dict) and data.get('passed') is True,'data':data})
 if len({x['filename'] for x in clean})!=len(clean):raise ValueError('Duplicate filenames in selection')
 row={'_id':n,'importedAt':datetime.now(timezone.utc).isoformat(),'allReportedPass':all(x['reportedPass'] for x in clean),'documents':clean}
 db.coursework_evidence.replace_one({'_id':n},row,upsert=True)
 return {'experiment':n,'importedAt':row['importedAt'],'files':len(clean),'status':'Imported: reports pass' if row['allReportedPass'] else 'Evidence imported'}

def export_evidence(db,n):
 if n not in REPOS:raise ValueError('Unknown experiment')
 row=db.coursework_evidence.find_one({'_id':n})
 if not row:raise ValueError('No imported evidence for this experiment')
 return {'experiment':n,'importedAt':row['importedAt'],'documents':row['documents'],'verification':'Student-provided JSON; not an independent rerun or registry check.'}
