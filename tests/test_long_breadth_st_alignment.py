import json
from pathlib import Path
import pytest
from long_breadth_st_alignment import analyze


def test_all_first_hits_and_counterexamples_keep_partial_window_separate():
    e=analyze();assert e==json.loads(Path('LONG_BREADTH_ST_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text());r=e['reading']
    assert r['common_days']==94 and r['signal_count']==6 and r['complete_signal_count']==5
    s={x['date']:x for x in r['signals']}
    assert set(s)=={'2026-07-08','2026-07-20','2026-09-04','2026-09-11','2026-09-24','2026-11-16'}
    assert s['2026-07-20']['st_pct']>0 and s['2026-07-20']['market_pct']>0
    assert s['2026-09-04']['st_pct']>0 and s['2026-09-04']['market_pct']<0
    assert s['2026-11-16']['observed_following_sessions']==3 and not s['2026-11-16']['complete_five']
    old=json.loads(Path('ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text())['reading']['signals']
    for x in old:
        assert s[x['date']]['st_pct']==pytest.approx(x['st_pct'],abs=1e-10)
        assert s[x['date']]['market_pct']==pytest.approx(x['market_pct'],abs=1e-10)
