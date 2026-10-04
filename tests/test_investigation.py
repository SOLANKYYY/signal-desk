import tempfile, unittest
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from backend.investigation import entities_for, labels, pdf_url
from backend.pdf_worker import extract

class InvestigationTests(unittest.TestCase):
    def test_cves_and_analyst_labels_stay_bounded_and_deduplicated(self):
        self.assertEqual(entities_for('cve-2024-12345 CVE-2024-12345 CVE-12-1', ['Example Actor','example actor']),
                         ['Example Actor','CVE-2024-12345'])
        self.assertEqual(len(labels([str(i) for i in range(100)])),40)
    def test_only_original_catalog_pdf_allowed(self):
        base='https://github.com/jacobdjwilson/awesome-annual-security-reports/blob/main/'
        self.assertIn('raw.githubusercontent.com',pdf_url(base+'Reports/Report%20Name.pdf'))
        for url in ['http://localhost/report.pdf',base+'../../private.pdf',base+'%2e%2e/private.pdf',
                    base+'report.html',base+'report.pdf?x=1',base.replace('github.com','github.com.evil.invalid')+'a.pdf']:
            with self.assertRaises(ValueError):pdf_url(url)
    def test_real_pdf_extraction_preserves_pdf_page_numbers(self):
        writer=PdfWriter()
        writer.add_blank_page(width=600,height=800)
        page=writer.add_blank_page(width=600,height=800)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 700 Td (CVE-2024-12345 is discussed, not confirmed locally.) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(stream)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.pdf'
            writer.write(path)
            data=extract(path)
        self.assertEqual(data['totalPages'],2)
        self.assertEqual(data['passages'][0]['page'],2)
        self.assertIn('CVE-2024-12345',data['passages'][0]['text'])
        self.assertFalse(data['limited'])
if __name__=='__main__':unittest.main()
