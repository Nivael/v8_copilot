import json
from pathlib import Path
from huawei_official_dividend_reading import reading

def test_saved_official_lookup_catalog_and_pdf_match_exact_mirror():
    r=reading()
    assert r==json.loads(Path('web/src/huaweiOfficialDividend.json').read_text())
    assert r['mirror_id']=='SINA-12649852' and r['official_id']=='1225611990'
    assert r['viewed_pages']==[1] and r['total_pages']==3
