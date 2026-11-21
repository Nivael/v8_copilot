from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
from pypdf import PdfReader


def test_guarantee_sources_and_capacity_are_not_cash_loss():
    e=json.loads(Path('NOV20_GUARANTEE_BODY_REVIEW_2026_11_21.json').read_text());pages=images=0
    for s in e['sources']:
        p=Path(s['source_store']);assert p.stat().st_size==s['bytes']and sha256(p.read_bytes()).hexdigest()==s['sha256']
        r=PdfReader(p);assert len(r.pages)==s['pages'];pages+=len(r.pages);assert s['codes'][0]in r.pages[0].extract_text()
        for page,h in s['visual_image_sha256'].items():
            assert int(page)in s['visual_physical_pages']
            assert sha256((p.parent/(h+'.png')).read_bytes()).hexdigest()==h;images+=1
    assert (pages,images)==(24,15)
    c=e['calculation_checks']
    assert D(c['weiling_before_wan'])+D(c['weiling_new_wan'])==D(c['weiling_after_wan'])
    assert D(c['weiling_cap_wan'])-D(c['weiling_after_wan'])==D(c['weiling_remaining_cap_wan'])
    assert sum(map(D,c['lianxiang_cap_parts_wan']))==D(c['lianxiang_cap_total_wan'])
    assert sum(map(D,c['kelida_proposed_caps_wan']))==1500 and D(c['kelida_actual_balance_wan'])==0
