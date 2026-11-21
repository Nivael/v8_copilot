import json
from pathlib import Path
from tianze_report_confirmation import reading

def test_later_official_confirmation_retains_original_debt_and_binds_saved_mirror():
    r=reading()
    assert r==json.loads(Path('web/src/tianzeReportConfirmation.json').read_text())
    assert r['published_on']=='2026-08-27' and r['effective_on']=='2026-06-02'
    assert r['original_official_bytes_recovered'] is False
    assert r['original_mirror_id']=='SINA-12361633' and r['page']==19


import pytest

@pytest.mark.parametrize('change,expected',[
    ('effective_date','confirmation dates'),
    ('report_date','confirmation dates'),
    ('redirect','official response identity'),
    ('mirror','mirror event identity'),
    ('debt','original notice debt'),
])
def test_rejects_changed_dates_identity_and_premature_debt_closure(tmp_path,change,expected):
    original=Path('TIANZE_OFFICIAL_REPORT_CONFIRMATION_2026_11_21.json');before=original.read_bytes();e=json.loads(before)
    if change=='effective_date':e['confirmation']['effective_on']='2026-06-03'
    elif change=='report_date':e['confirmation']['reported_on']='2026-06-02'
    elif change=='redirect':e['source']['final_url']='https://example.com/report.pdf'
    elif change=='mirror':e['original_mirror_id']='SINA-12329033'
    elif change=='debt':e['original_announcement_official_bytes_recovered']=True
    candidate=tmp_path/'candidate.json';candidate.write_text(json.dumps(e,ensure_ascii=False))
    with pytest.raises(ValueError,match=expected):reading(candidate)
    assert original.read_bytes()==before
