"""Re-extract/re-render the reviewed issuer page; never write source or reading data.
Run with: uv run --no-project --with pypdfium2 --with pillow python verify_tianze_pdf_page.py
"""
from pathlib import Path
from hashlib import sha256
from io import BytesIO
import json
import pypdfium2 as pdf


def verify(path=Path('TIANZE_OFFICIAL_REPORT_CONFIRMATION_2026_11_21.json')):
    e=json.loads(Path(path).read_text());s=e['source'];store=Path(s['source_store']);raw=(store/(s['sha256']+'.pdf')).read_bytes()
    if sha256(raw).hexdigest()!=s['sha256'] or len(raw)!=s['bytes']:raise ValueError('PDF bytes differ')
    doc=pdf.PdfDocument(raw)
    try:
        if len(doc)!=e['total_pages']:raise ValueError('PDF page count differs')
        page=doc[e['selected_page']-1]
        try:
            text_page=page.get_textpage()
            try:text=text_page.get_text_range()
            finally:text_page.close()
            if text!=e['selected_page_text'] or sha256(text.encode()).hexdigest()!=e['selected_page_text_sha256']:raise ValueError('PDF extracted page text differs')
            bitmap=page.render(scale=1.4)
            try:
                picture=bitmap.to_pil();buffer=BytesIO();picture.save(buffer,format='PNG');image=buffer.getvalue()
            finally:bitmap.close()
            retained=(store/(e['selected_page_image_sha256']+'.png')).read_bytes()
            if image!=retained or sha256(image).hexdigest()!=e['selected_page_image_sha256']:raise ValueError('PDF rendered page differs; review renderer/version before replacing evidence')
        finally:page.close()
    finally:doc.close()
    return dict(version='tianze_pdf_page_replay_v1',source_sha256=s['sha256'],total_pages=e['total_pages'],reviewed_page=e['selected_page'],text_exact=True,image_exact=True,original_notice_debt_closed=False,scope='One selected page re-extracted/rendered; not whole-report review or a new independent case')

if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))
