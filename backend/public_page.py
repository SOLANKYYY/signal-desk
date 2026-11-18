"""Bounded public HTTPS text retrieval with DNS-pinned TLS and redirect checks."""
import http.client, ipaddress, re, socket, ssl
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, urlunsplit

class PageError(ValueError): pass

def target(url):
    if not isinstance(url,str) or len(url)>1600: raise PageError('Use a public HTTPS link under 1,600 characters.')
    if any(ord(c)<33 for c in url): raise PageError('The link contains invalid characters.')
    try:
        u=urlsplit(url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):raise ValueError()
        host=u.hostname.encode('idna').decode('ascii')
        if host.endswith('.') or '%' in host:raise ValueError()
    except (ValueError,UnicodeError):raise PageError('Use an HTTPS website link without a login or custom port.') from None
    try:addresses=sorted({x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
    except OSError:raise PageError('The website address could not be found.') from None
    if not addresses or any(not ipaddress.ip_address(x).is_global or ipaddress.ip_address(x).is_multicast for x in addresses):
        raise PageError('Private, local and reserved network addresses cannot be read.')
    return host,addresses[0],urlunsplit(('https','['+host+']' if ':' in host else host,u.path or '/',u.query,''))

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip):super().__init__(host,timeout=8,context=ssl.create_default_context());self.ip=ip
    def connect(self):
        sock=socket.create_connection((self.ip,443),timeout=self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:sock.close();raise

class Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.skip=0;self.in_title=False;self.title=[];self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','svg','template'):self.skip+=1
        if tag=='title':self.in_title=True
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','svg','template'):self.skip=max(0,self.skip-1)
        if tag=='title':self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if not self.skip:self.parts.append(data)

def read_page(url):
    for redirect in range(4):
        host,ip,clean=target(url);u=urlsplit(clean);conn=PinnedHTTPS(host,ip)
        try:
            conn.request('GET',u.path+('?' + u.query if u.query else ''),headers={'User-Agent':'SignalDesk/1.0 public-evidence-reader','Accept':'text/html,text/plain','Accept-Encoding':'identity'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location or redirect==3:raise PageError('The website redirects too many times.')
                url=urljoin(clean,location);continue
            if response.status!=200:raise PageError('The website could not be read. Paste a public excerpt instead.')
            kind=(response.getheader('Content-Type') or '').split(';')[0].lower()
            if kind not in ('text/html','text/plain','application/xhtml+xml'):raise PageError('Use an HTML or plain-text page. Paste an excerpt for PDFs or other files.')
            if response.getheader('Content-Encoding','identity').lower() not in ('','identity'):raise PageError('The website uses an unsupported content encoding.')
            raw=response.read(1000001)
            if len(raw)>1000000:raise PageError('The page is too large. Paste the relevant excerpt instead.')
            parser=Text();decoded=raw.decode('utf-8',errors='replace')
            if kind=='text/plain':text=decoded;title=host
            else:parser.feed(decoded);text=' '.join(parser.parts);title=' '.join(parser.title) or host
            text=re.sub(r'\s+',' ',text).strip()[:12000]
            if len(text)<20:raise PageError('No readable text was found. Paste an excerpt instead.')
            return {'title':title[:300],'text':text,'url':clean,'platform':'unknown','stage':'unassessed','provenance':'User-requested public HTTPS page; bounded excerpt, not verified facts'}
        except PageError:raise
        except (OSError,http.client.HTTPException):raise PageError('The website did not respond safely in time. Paste an excerpt instead.') from None
        finally:conn.close()
