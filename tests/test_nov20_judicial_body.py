from pathlib import Path
from decimal import Decimal as D
from hashlib import sha256
import json
from pypdf import PdfReader


def test_judicial_sources_and_reported_arithmetic_preserve_event_boundaries():
    e=json.loads(Path('NOV20_JUDICIAL_BODY_REVIEW_2026_11_21.json').read_text())
    assert e['catalog_review_sha256']==sha256(Path('NOV20_FIXED_CATALOG_REVIEW_2026_11_21.json').read_bytes()).hexdigest()
    pages=images=0
    for s in e['sources']:
        p=Path(s['source_store']);assert p.stat().st_size==s['bytes']and sha256(p.read_bytes()).hexdigest()==s['sha256']
        r=PdfReader(p);assert len(r.pages)==s['pages'];pages+=len(r.pages)
        assert s['codes'][0]in r.pages[0].extract_text()
        for page,h in s['visual_image_sha256'].items():
            assert int(page)in s['visual_physical_pages']
            assert sha256((p.parent/(h+'.png')).read_bytes()).hexdigest()==h
            images+=1
    assert (pages,images)==(11,9)
    c=e['calculation_checks']
    assert sum(map(D,c['ruimao_case_amounts_wan']))==D(c['ruimao_declared_total_wan'])
    assert c['xilinmen_auction_shares']==15616487
    assert c['xilinmen_conditional_remaining_shares']==118293747
