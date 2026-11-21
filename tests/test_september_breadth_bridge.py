import json
from pathlib import Path
from build_september_breadth_bridge import build


def test_three_day_bridge_replays_both_venues_and_six_halt_days():
    e=build()
    assert e==json.loads(Path('SEPTEMBER_BREADTH_BRIDGE_EVIDENCE_2026_11_21.json').read_text())
    assert [p['date']for p in e['points']]==['2026-09-01','2026-09-02','2026-09-03']
    assert sum(len(p['missing_prices_classified_as_halted'])for p in e['points'])==6
    for p in e['points']:
        assert not p['unexplained_missing']
        for key in ['observed_trading_stocks','listed_source_stocks','nontrading_stocks','advancing','declining','flat']:
            assert p['all'][key]==p['SSE'][key]+p['SZSE'][key]
