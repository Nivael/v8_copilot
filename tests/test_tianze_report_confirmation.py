import json
from pathlib import Path
from tianze_report_confirmation import reading

def test_later_official_confirmation_retains_original_debt_and_binds_saved_mirror():
    r=reading()
    assert r==json.loads(Path('web/src/tianzeReportConfirmation.json').read_text())
    assert r['published_on']=='2026-08-27' and r['effective_on']=='2026-06-02'
    assert r['original_official_bytes_recovered'] is False
    assert r['original_mirror_id']=='SINA-12361633' and r['page']==19
