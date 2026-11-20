from pathlib import Path
import json
import pytest
from long_breadth_confirmation_cost import analyze_cost


def test_all_confirmation_windows_keep_rebound_and_positive_st_exception():
    e=analyze_cost();assert e==json.loads(Path('LONG_CONFIRMATION_COST_EVIDENCE_2026_11_21.json').read_text())
    rows={r['signal_date']:r for r in e['reading']['rows']};assert len(rows)==6
    assert all(r['already_market_pct']<0 for r in rows.values())
    assert rows['2026-09-04']['already_st_pct']>0
    assert rows['2026-07-20']['already_st_pct']==pytest.approx(-8.393799154537835)
    assert rows['2026-07-20']['following_st_pct']>0 and rows['2026-07-20']['following_market_pct']>0
    old=json.loads(Path('ST_BREADTH_TIMING_EVIDENCE_2026_11_21.json').read_text())['reading']['rows']
    for r in old:
        assert rows[r['signal_date']]['already_st_pct']==pytest.approx(r['already_st_pct'],abs=1e-10)
