from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
from pypdf import PdfReader


def test_full_sources_keep_B_share_scope_and_additional_collateral_item():
    e=json.loads(Path('NOV20_VOLATILITY_BOARD_BODY_REVIEW_2026_11_21.json').read_text());pages=images=0
    for s in e['sources']:
        p=Path(s['source_store']);assert p.stat().st_size==s['bytes']and sha256(p.read_bytes()).hexdigest()==s['sha256']
        r=PdfReader(p);pages+=len(r.pages)
        assert s['codes'][0]in r.pages[0].extract_text()
        for page,h in s['visual_image_sha256'].items():
            assert int(page)in s['visual_physical_pages']
            assert sha256((p.parent/(h+'.png')).read_bytes()).hexdigest()==h;images+=1
    assert (pages,images)==(14,14)
    c=e['calculation_checks']
    assert sum(map(D,c['chunxing_receivable_parts_wan']))==D(c['chunxing_receivable_sum_wan'])==D('36532.74')
    assert e['classification']['1225680178']=='B_share_specific_notice_not_A_share_trigger'
    assert e['classification']['1225679972']=='board_resolution_with_additional_substantive_collateral_item'
