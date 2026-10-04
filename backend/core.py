"""Shared schema, deterministic triage, ingestion parsers and cache calculations."""
import hashlib, html, re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

REPO = 'https://github.com/jacobdjwilson/awesome-annual-security-reports'
README_URL = 'https://raw.githubusercontent.com/jacobdjwilson/awesome-annual-security-reports/main/README.md'
CTI_URL = 'https://ctidigest.com/'
VERDICTS = ('needs-review', 'confirmed-threat', 'benign')
CATEGORIES = ('ransomware', 'phishing', 'vulnerability', 'malware', 'general')

def now(): return datetime.now(timezone.utc)
def key(value): return hashlib.sha256(value.encode()).hexdigest()[:24]
def clean(value): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value or ''))).strip()
def safe_url(value, base=''):
    u = urlsplit(urljoin(base, value))
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
        return None
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path, u.query, ''))

def classify(title, summary=''):
    text = (title + ' ' + summary).lower()
    rules = [('ransomware', r'\bransomware\b|\bextortion\b'),
             ('phishing', r'\bphishing\b|\bcredential theft\b'),
             ('vulnerability', r'\bcve-\d{4}-\d+\b|\bvulnerabilit\w*\b|\bzero.day\b'),
             ('malware', r'\bmalware\b|\btrojan\b|\bbotnet\b')]
    matches = [(category, re.findall(pattern, text)) for category, pattern in rules]
    matches = [(c, sorted(set(m))) for c,m in matches if m]
    return {'category': matches[0][0] if matches else 'general',
            'matchedTerms': [x for _, terms in matches for x in terms][:12],
            'method': 'keyword-triage-v1', 'verdict': 'needs-review',
            'note': 'Topic detection only; an analyst must verify threat evidence.'}

def parse_annual(markdown):
    """Extract metadata only from annual-report bullets, not TOC/resources links."""
    out, seen = [], set()
    pattern = re.compile(r'^- \[([^\]]+)\]\(([^\s]+)\)\s*-\s*\[([^\]]+)\]\(([^\s]+)\)\s*\((20\d{2})\)')
    for line in markdown.splitlines():
        m=pattern.match(line.strip())
        if not m: continue
        publisher, publisher_url, title, path, year=m.groups()
        url=safe_url(path, REPO+'/blob/main/')
        publisher_url=safe_url(publisher_url)
        if not url or not publisher_url or url in seen: continue
        seen.add(url)
        out.append({'title':clean(title), 'publisher':clean(publisher), 'publisherUrl':publisher_url,
                    'url':url, 'year':int(year), 'kind':'annual-report',
                    'summary':'Annual security report metadata. Open the original publication to evaluate its findings.',
                    'origin':REPO, 'synthetic':False})
    return out

def cache_sample(status):
    c=status.get('wiredTiger',{}).get('cache',{})
    names={'bytes':'bytes currently in the cache','maximumBytes':'maximum bytes configured',
           'pagesRequested':'pages requested from the cache','pagesRead':'pages read into cache',
           'dirtyBytes':'tracked dirty bytes in the cache',
           'applicationEvictions':'eviction pages evicted by application threads'}
    result={k:c.get(v) for k,v in names.items()}
    result.update(at=now().isoformat(), uptime=status.get('uptimeMillis'))
    result['occupancyPct']=(100*result['bytes']/result['maximumBytes']
                            if result['bytes'] is not None and result['maximumBytes'] else None)
    return result

def cache_delta(previous, current):
    result=dict(current, hitRatioPct=None, pagesRequestedDelta=None, pagesReadDelta=None, reason=None)
    if not previous: result['reason']='First sample: waiting for an interval.'; return result
    if (current.get('uptime') is not None and previous.get('uptime') is not None
        and current['uptime'] < previous['uptime']):
        result['reason']='Server restarted; interval discarded.'; return result
    if any(x.get(k) is None for x in (previous,current) for k in ('pagesRequested','pagesRead')):
        result['reason']='WiredTiger counters unavailable.'; return result
    requests=current['pagesRequested']-previous['pagesRequested']
    reads=current['pagesRead']-previous['pagesRead']
    result.update(pagesRequestedDelta=requests,pagesReadDelta=reads)
    if requests<=0 or reads<0 or reads>requests:
        result['reason']='Idle, reset, or incomparable page counters; ratio unavailable.'
    else: result['hitRatioPct']=100*(1-reads/requests)
    return result
