from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
from pypdf import PdfReader


def test_shareholder_sources_and_money_roles_are_separately_retained():
    e=json.loads(Path('NOV20_SHAREHOLDER_BODY_REVIEW_2026_11_21.json').read_text());pages=images=0
    for s in e['sources']:
        p=Path(s['source_store']);assert p.stat().st_size==s['bytes']and sha256(p.read_bytes()).hexdigest()==s['sha256']
        r=PdfReader(p);pages+=len(r.pages);assert s['codes'][0]in r.pages[0].extract_text()
        for page,h in s['visual_image_sha256'].items():
            assert int(page)in s['visual_physical_pages']
            assert sha256((p.parent/(h+'.png')).read_bytes()).hexdigest()==h;images+=1
    assert (pages,images)==(9,7)
    c=e['calculation_checks']
    assert c['meili_after_shares']-c['meili_before_shares']==c['meili_added_shares']==3500000
    average=D(c['guozhong_buyback_yuan'])/D(c['guozhong_buyback_shares'])
    assert D('1.02')<=average<=D('1.07')
