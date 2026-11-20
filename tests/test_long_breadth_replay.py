from pathlib import Path
import json
import pytest
from build_long_breadth_replay import build,project


def test_every_historical_day_is_prefix_invariant():
    e=json.loads(Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json').read_text())
    full=project(e['points'])
    for stop in range(1,len(full)+1):
        assert project(e['points'][:stop])==full[:stop]
    assert build()==json.loads(Path('web/src/longBreadthReplay.json').read_text())
    assert len(full)==97
    assert [r['date']for r in full if r['third_day_first_signal']]==['2026-07-08','2026-07-20','2026-09-04','2026-09-11','2026-09-24','2026-11-16']


def test_invalid_denominator_is_rejected():
    e=json.loads(Path('LONG_MARKET_BREADTH_EVIDENCE_2026_11_21.json').read_text())
    e['points'][0]['all']['observed_trading_stocks']+=1
    with pytest.raises(ValueError,match='denominator'):project(e['points'])
