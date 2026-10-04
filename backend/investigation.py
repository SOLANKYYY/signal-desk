"""Local investigation features using the existing catalog and configured feeds."""
import json, re, subprocess, sys, tempfile, urllib.request, threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, unquote
from .core import key, now
from .db import db

CVE = re.compile(r'\bCVE-\d{4}-\d{4,}\b', re.I)
MAX_PDF_BYTES = 20 * 1024 * 1024

def labels(values):
    result = {}
    for value in values:
        value = ' '.join(str(value).split()).strip()[:100]
        if value: result.setdefault(value.casefold(), value.upper() if CVE.fullmatch(value) else value)
    return list(result.values())[:40]

def entities_for(text, manual=()):
    return labels(list(manual) + CVE.findall(text))

def report_entities(report):
    return entities_for(report.get('title', '') + ' ' + report.get('summary', ''), report.get('analystEntities', []))

def migrate_entities():
    # Additive migration. Existing verdicts, notes, and analyst labels are retained.
    for report in db.reports.find({'entities': {'$exists': False}}):
        db.reports.update_one({'_id': report['_id']}, {'$set': {'entities': report_entities(report)}})

def entity_profiles():
    rows = db.reports.aggregate([
        {'$match': {'provenance.synthetic': {'$ne': True}}},
        {'$unwind': '$entities'},
        {'$group': {'_id': {'$toLower': '$entities'}, 'name': {'$first': '$entities'},
                    'reports': {'$sum': 1}, 'lastSeen': {'$max': '$ingestedAt'}}},
        {'$sort': {'reports': -1, '_id': 1}}, {'$limit': 100}])
    return list(rows)

def related_profile(name):
    if not name or len(name) > 100: raise ValueError('Choose a valid entity label')
    query = {'entities': re.compile('^' + re.escape(name) + '$', re.I), 'provenance.synthetic': {'$ne': True}}
    reports = list(db.reports.find(query).sort('ingestedAt', -1).limit(100))
    ids = [r['_id'] for r in reports]
    evidence = list(db.evidence_passages.find({'reportId': {'$in': ids},
                    'text': re.compile(re.escape(name), re.I)}, {'_id': 0}).limit(30))
    return {'name': name, 'total': db.reports.count_documents(query), 'reports': reports, 'evidence': evidence,
            'note': 'Labels and document mentions are research leads, not a confirmed incident or worldwide ranking.'}

def search_query(q):
    """Literal matching preserves punctuation in CVEs, IPs, domains, URLs and hashes."""
    value = q.strip()[:200]
    if not value: return {}
    pattern = re.compile(re.escape(value), re.I)
    indicators = [x['_id'] for x in db.indicators.find({'value': pattern}, {'_id': 1}).limit(1000)]
    ids = db.observations.distinct('reportId', {'indicatorId': {'$in': indicators}}) if indicators else []
    ids += db.evidence_passages.distinct('reportId', {'text': pattern})
    return {'$or': [{field: pattern} for field in ('title', 'summary', 'url', 'entities')] + [{'_id': {'$in': ids}}]}

def pdf_url(url):
    """Only PDFs already cataloged in our original annual-report repository."""
    u = urlsplit(url)
    prefix = '/jacobdjwilson/awesome-annual-security-reports/blob/main/'
    if (u.scheme != 'https' or u.netloc != 'github.com' or not u.path.startswith(prefix)
            or not unquote(u.path).lower().endswith('.pdf') or u.query or u.fragment
            or '..' in unquote(u.path).split('/')):
        raise ValueError('PDF indexing supports cataloged PDFs in the original annual-report repository only.')
    return 'https://raw.githubusercontent.com/' + u.path[1:].replace('/blob/main/', '/main/', 1)

class CatalogRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urlsplit(newurl)
        if u.scheme != 'https' or u.netloc != 'raw.githubusercontent.com':
            raise ValueError('PDF download redirected outside the catalog host')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

_pdf_lock=threading.Lock()

def index_pdf(report_id):
    with _pdf_lock:
        result=_index_pdf(report_id)
        from .alerts import analyze_report
        analyze_report(report_id)
        return result

def _index_pdf(report_id):
    report = db.reports.find_one({'_id': report_id, 'kind': 'annual-report'})
    if not report: raise ValueError('Select an annual report from the catalog')
    url = pdf_url(report['url'])
    if report.get('pdf', {}).get('status') == 'indexed':
        return {'reportId': report_id, **report.get('pdf', {}), 'status': 'already-indexed'}
    request = urllib.request.Request(url, headers={'User-Agent': 'SignalDesk/2.0'})
    with urllib.request.build_opener(CatalogRedirect).open(request, timeout=30) as response:
        data = response.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES: raise ValueError('PDF exceeds the 20 MiB download limit')
    if not data.lstrip().startswith(b'%PDF-'): raise ValueError('Source did not return a PDF')
    # Parse in a separate, timed process; never execute or follow PDF attachments/links.
    with tempfile.TemporaryDirectory(prefix='signal-pdf-') as folder:
        path = Path(folder) / 'report.pdf'; path.write_bytes(data)
        result = subprocess.run([sys.executable, '-m', 'backend.pdf_worker', str(path)],
                                capture_output=True, text=True, encoding='utf-8', timeout=90)
    if result.returncode: raise ValueError('PDF extraction failed; the document may be encrypted or unsupported')
    extracted = json.loads(result.stdout)
    passages = extracted.pop('passages')
    if not passages: raise ValueError('No selectable text found. Scanned documents require OCR, which is not included.')
    docs = [{'_id': key(report_id + ':' + str(i)), 'reportId': report_id, 'title': report['title'],
             'url': report['url'], 'page': p['page'], 'text': p['text'], 'indexedAt': now()}
            for i, p in enumerate(passages)]
    for doc in docs: db.evidence_passages.replace_one({'_id': doc['_id']}, doc, upsert=True)
    # Re-read so reviews made while extraction ran are not overwritten.
    current = db.reports.find_one({'_id': report_id})
    entities = entities_for(' '.join(p['text'] for p in passages), report_entities(current))
    status = dict(extracted, passages=len(docs), indexedAt=now(), status='indexed')
    db.reports.update_one({'_id': report_id}, {'$set': {'pdf': status, 'entities': entities,
        'pdfEntities': labels(CVE.findall(' '.join(p['text'] for p in passages)))}})
    return {'reportId': report_id, **status}

def evidence_search(value, page=1):
    value = value.strip()[:200]
    query = {'text': re.compile(re.escape(value), re.I)} if value else {}
    total = db.evidence_passages.count_documents(query)
    return {'items': list(db.evidence_passages.find(query, {'_id': 0}).sort([('reportId', 1), ('page', 1)]).skip((page-1)*15).limit(15)),
            'total': total, 'page': page, 'pageSize': 15,
            'indexedReports': db.reports.count_documents({'pdf.status': 'indexed'})}
