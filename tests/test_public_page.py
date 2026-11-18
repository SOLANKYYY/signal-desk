import unittest
from unittest.mock import patch,MagicMock
from backend import public_page as p

class PublicPageTests(unittest.TestCase):
    def test_rejects_private_and_mixed_dns(self):
        for addresses in [['127.0.0.1'],['169.254.169.254'],['93.184.216.34','10.0.0.1'],['::1']]:
            with self.subTest(addresses=addresses),patch.object(p.socket,'getaddrinfo',return_value=[(2,1,6,'',(x,443)) for x in addresses]):
                with self.assertRaises(p.PageError):p.target('https://public.example/page')
    def test_rejects_bad_schemes_credentials_ports(self):
        for url in ['http://example.org','https://u:p@example.org/','https://example.org:8080/','https://example.org/\r\nHost:local','file:///etc/passwd']:
            with self.subTest(url=url),self.assertRaises(p.PageError):p.target(url)
    def test_pins_resolved_ip_and_preserves_tls_hostname(self):
        with patch.object(p.socket,'create_connection') as create,patch.object(p.ssl,'create_default_context') as context:
            c=p.PinnedHTTPS('example.org','93.184.216.34');c.connect()
            create.assert_called_once_with(('93.184.216.34',443),timeout=8)
            context.return_value.wrap_socket.assert_called_once_with(create.return_value,server_hostname='example.org')
    def test_redirect_revalidates_destination(self):
        response=MagicMock(status=302);response.getheader.return_value='https://127.0.0.1/secret'
        with patch.object(p,'target',side_effect=[('example.org','93.184.216.34','https://example.org/'),p.PageError('blocked')]) as target,patch.object(p,'PinnedHTTPS') as conn:
            conn.return_value.getresponse.return_value=response
            with self.assertRaises(p.PageError):p.read_page('https://example.org/')
            self.assertEqual(target.call_count,2)
    def test_extracts_text_and_ignores_scripts(self):
        response=MagicMock(status=200);response.getheader.side_effect=lambda name,*args: {'Content-Type':'text/html','Content-Encoding':'identity'}.get(name)
        response.read.return_value=b'<title>Advice</title><script>hidden exploit</script><p>Read the official advisory before making changes.</p>'
        with patch.object(p,'target',return_value=('example.org','93.184.216.34','https://example.org/')),patch.object(p,'PinnedHTTPS') as conn:
            conn.return_value.getresponse.return_value=response;d=p.read_page('https://example.org/')
            self.assertNotIn('hidden exploit',d['text']);self.assertEqual(d['title'],'Advice')
    def test_oversize_and_nontext_rejected(self):
        for mime,data in [('application/pdf',b'x'*30),('text/plain',b'x'*1000001)]:
            r=MagicMock(status=200);r.getheader.side_effect=lambda key,*a: mime if key=='Content-Type' else 'identity';r.read.return_value=data
            with patch.object(p,'target',return_value=('example.org','93.184.216.34','https://example.org/')),patch.object(p,'PinnedHTTPS') as conn:
                conn.return_value.getresponse.return_value=r
                with self.assertRaises(p.PageError):p.read_page('https://example.org/')

if __name__=='__main__':unittest.main()
