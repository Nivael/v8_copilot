from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
from pypdf import PdfReader


def test_source_identity_critical_images_and_arithmetic():
    e = json.loads(Path('NOV20_CHUNXING_BODY_REVIEW_2026_11_21.json').read_text())
    assert e['catalog_review_sha256'] == sha256(Path('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json').read_bytes()).hexdigest()
    total = images = 0
    for s in e['sources']:
        p = Path(s['source_store'])
        assert sha256(p.read_bytes()).hexdigest() == s['sha256'] and p.stat().st_size == s['bytes']
        r = PdfReader(p)
        assert len(r.pages) == s['pages']
        total += len(r.pages)
        assert '002547' in r.pages[0].extract_text()
        for page, signature in s['visual_image_sha256'].items():
            assert int(page) in s['visual_physical_pages']
            assert sha256((p.parent / (signature + '.png')).read_bytes()).hexdigest() == signature
            images += 1
    assert (total, images) == (e['text_pages'], e['critical_visual_pages']) == (16, 11)
    c = e['calculation_checks']
    assert D(c['new_settlement_debt']) - D(c['new_settlement_payment']) == D(c['new_settlement_conditional_relief']) == D('1617439.90')
    assert D(c['interest_relief_detail']) == D('2308590.28')
    assert D(c['cumulative_remaining_relief_wan']) == D('2525.23')
