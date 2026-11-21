import json
from pathlib import Path
from build_early_market_breadth import build


def test_two_venue_early_window_replays_and_reconciles_each_denominator():
    e=json.loads(Path('EARLY_MARKET_BREADTH_EVIDENCE_2026_11_21.json').read_text())
    assert build(e['szse_source_folder'])==e
    assert e['sessions']==len(e['points'])==44
    assert e['start']=='2026-07-01'and e['through']=='2026-08-31'
    assert sum(len(p['missing_prices_classified_as_halted'])for p in e['points'])==90
    for p in e['points']:
        assert p['unexplained_missing']==[]
        for key in ['observed_trading_stocks','listed_source_stocks','nontrading_stocks','advancing','declining','flat','declining_5pct_or_more']:
            assert p['all'][key]==p['SSE'][key]+p['SZSE'][key]
        assert p['all']['advancing']+p['all']['declining']+p['all']['flat']==p['all']['observed_trading_stocks']
