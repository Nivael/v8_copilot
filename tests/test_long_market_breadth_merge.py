import copy
import json
from pathlib import Path
import pytest
from merge_long_market_breadth import merge


def windows():
    e=json.loads(Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json').read_text())
    return e,[{'points':e['points'][:44]},{'points':e['points'][44:47]},{'points':e['points'][47:]}]


def test_calendar_and_old_fifty_day_totals_remain_exact():
    e,w=windows();assert merge(*w)==e['points'] and len(e['points'])==97
    old=json.loads(Path('MARKET_RECENT_BREADTH_EVIDENCE_2026_11_21.json').read_text())['merged_history']['points']
    assert [(p['date'],p['all'])for p in w[2]['points']]==[(p['date'],p['all'])for p in old]
    assert set(e['supplemental_venue_bindings'])=={'2026-11-05','2026-11-06'}


def test_missing_bridge_overlap_and_false_denominator_are_rejected():
    _,w=windows();w[1]['points'].pop()
    with pytest.raises(ValueError,match='missing trading'):merge(*w)
    _,w=windows();w[1]['points'][0]=copy.deepcopy(w[0]['points'][-1])
    with pytest.raises(ValueError,match='overlap'):merge(*w)
    _,w=windows();w[0]['points'][0]['SSE']['advancing']+=1
    with pytest.raises(ValueError,match='denominator'):merge(*w)
