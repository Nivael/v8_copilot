import json
from decimal import Decimal as D
from pathlib import Path
from fixed_limit_transition import analyze


def test_same_members_and_exhaustive_transition_matrix_reconcile_with_price_changes():
    result=analyze()
    assert result==json.loads(Path('FIXED_LIMIT_TRANSITION_2026_11_21.json').read_text())
    assert result['paired']==146 and len(result['excluded'])==4
    matrix=result['closing_state_matrix']
    assert matrix==dict(stayed_lower=1,left_lower=6,new_lower=1,neither_lower=138)
    assert sum(matrix.values())==146
    assert matrix['stayed_lower']+matrix['left_lower']==result['previous']['close_lower']==7
    assert matrix['stayed_lower']+matrix['new_lower']==result['current']['close_lower']==2
    assert result['up']==24 and result['down']==115 and result['flat']==7
    leaving=[r for r in result['rows'] if r['previous_close_lower'] and not r['current_close_lower']]
    assert len(leaving)==6
    assert sum(D(r['change_pct'])<0 for r in leaving)==5
    assert sum(D(r['change_pct'])>0 for r in leaving)==1
    assert {r['code'] for r in leaving}==set(result['left_close_lower']['codes'])


def test_registered_reading_matches_replayed_transition():
    from build_fixed_limit_transition_reading import reading
    assert reading()==json.loads(Path('web/src/fixedLimitTransition.json').read_text())
