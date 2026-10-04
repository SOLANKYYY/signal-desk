"""Bounded plain-text extraction worker. No OCR, attachments, links or scripts."""
import json, sys
from pypdf import PdfReader

def extract(path):
    reader = PdfReader(path)
    if reader.is_encrypted: raise ValueError('Encrypted PDF')
    passages = []; remaining = 500000; scanned = 0
    for page_number, page in enumerate(reader.pages[:120], 1):
        if remaining <= 0: break
        raw = page.extract_text() or ''
        text = ' '.join(raw.split())[:remaining]
        remaining -= len(text); scanned = page_number
        for offset in range(0, len(text), 900):
            chunk = text[offset:offset+1000]
            if chunk.strip(): passages.append({'page': page_number, 'text': chunk})
    return {'passages': passages, 'totalPages': len(reader.pages), 'pagesProcessed': scanned,
            'limited': len(reader.pages)>120 or remaining<=0,
            'method': 'pypdf plain text; PDF page numbers; no OCR'}
if __name__ == '__main__':
    print(json.dumps(extract(sys.argv[1]), ensure_ascii=True))
