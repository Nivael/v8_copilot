import copy
import json
from pathlib import Path
import pytest
from breadth_wait_comparison import compare


def source():
    return json.loads(Path('ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text())


def test_all_short_spells_and_boundary_are_retained():
    r = compare(source())
    assert r['observed_sessions'] == 49
    assert len(r['episodes']) == 15
    assert r['episodes'][0]['left_boundary_unknown']
    assert sum(ep['observed_weak_sessions'] < 3 for ep in r['episodes']) == 12
    assert r['episodes'][-1]['ongoing_at_cutoff']
    assert r['episodes'][-1]['observed_weak_sessions'] == 6
    assert [c['following_sessions'] for c in r['episodes'][-1]['checks']] == [5, 4, 3]
    assert r['episodes'][-1]['checks'][1]['five_market_pct'] is None
    assert r['episodes'][-1]['checks'][1]['partial_market_pct'] is not None


def test_matches_existing_three_day_results_and_compounding():
    e = source(); r = compare(e)
    signals = {s['date']: s for s in e['reading']['signals']}
    for ep in r['episodes']:
        c = ep['checks'][2]
        if not c['formed']:
            continue
        s = signals[c['date']]
        assert c['five_market_pct'] == s['five_market_pct']
        assert c['five_st_pct'] == s['five_st_pct']
    nov = r['episodes'][-1]
    assert nov['anchor'] == '2026-11-11'
    assert nov['checks'][2]['already_market_pct'] == pytest.approx(-4.763770325358413)
    assert r['episodes'][1]['checks'][2]['five_market_pct'] > 0
    assert r['episodes'][1]['checks'][0]['five_market_pct'] < 0


def test_rejects_changed_frozen_result_or_invalid_calendar():
    e = source(); e['reading']['common_days'] = 48
    with pytest.raises(ValueError, match='replay'): compare(e)
    e = source(); e['inputs']['breadth_days'].pop(2)
    with pytest.raises(ValueError, match='calendar'): compare(e)
    e = source(); e['inputs']['breadth_days'][0]['trading'] = 0
    with pytest.raises(ValueError, match='denominator'): compare(e)
