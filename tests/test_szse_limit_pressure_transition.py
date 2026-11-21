import json
from pathlib import Path
from szse_limit_pressure_transition import analyze


def test_same_subset_has_fewer_limit_closes_but_majority_still_falls():
    result=analyze()
    assert result==json.loads(Path('SZSE_LIMIT_PRESSURE_TRANSITION_EVIDENCE_2026_11_21.json').read_text())
    r=result['reading']
    assert len({x['symbol']for x in r['rows']})==r['paired']==71
    assert r['previous']['close_lower']==2 and r['current']['close_lower']==0
    assert r['up']+r['down']+r['flat']==71 and r['down']==51
    assert r['median_display']=='-2.43%'
    assert not r['complete_coverage']
    assert {x['symbol']for x in r['excluded']}=={'000010.SZ','002122.SZ','002717.SZ'}
