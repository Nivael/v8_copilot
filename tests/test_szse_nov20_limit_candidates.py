import json
from pathlib import Path
import pytest
from verify_szse_nov20_limit_candidates import verify


def data():
    return json.loads(Path('SZSE_NOV20_LIMIT_CANDIDATES_2026_11_21.json').read_text())


def test_partial_coverage_and_no_trade_remain_distinct():
    r=verify(data())
    assert r['counts']==dict(matched=71,official_no_trade_excluded=2,unresolved=1)
    assert not r['complete_trading_coverage']
    assert r['hits']['close_lower']==[]
    assert set(r['hits']['touch_lower'])=={'000826.SZ','002082.SZ'}


def test_omitted_member_and_unknown_as_negative_are_rejected():
    e=data();e['rows']=[r for r in e['rows']if r['status']!='unresolved']
    with pytest.raises(ValueError,match='scope'):verify(e)
    e=data();next(r for r in e['rows']if r['status']=='unresolved')['reading']={'close_lower':False}
    with pytest.raises(ValueError,match='unresolved'):verify(e)
