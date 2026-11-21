import json
from pathlib import Path
from audit_early_sse_price_gaps import audit


def test_raw_replay_keeps_listed_but_absent_exit_days_unknown():
    e=audit()
    assert e==json.loads(Path('EARLY_SSE_PRICE_GAP_AUDIT_2026_11_21.json').read_text())
    assert e['selected_price_sources']==2318
    assert len(e['missing_active_days'])==90
    assert len({r['code']for r in e['missing_active_days']})==25
    assert not e['zero_volume_days']
    assert [r['date']for r in e['missing_active_days']if r['code']=='600193']==['2026-07-01','2026-07-02','2026-07-03']
    assert [r['date']for r in e['missing_active_days']if r['code']=='600608']==['2026-07-01','2026-07-02']
