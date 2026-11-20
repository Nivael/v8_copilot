from pathlib import Path
from decimal import Decimal as D
import json
import pytest
from long_index_price_replay import build,derive


def test_sources_and_all_prefixes_preserve_daily_state():
    e=build()
    assert e==json.loads(Path('LONG_INDEX_PRICE_REPLAY_EVIDENCE_2026_11_21.json').read_text())
    assert len(e['rows'])==97 and e['overlapping_closes_matched']==65
    prices=[dict(date=r['date'],close=r['close'])for r in e['rows']]
    for end in range(1,98):assert derive(prices[:end])==e['rows'][:end]
    last=e['rows'][-1]
    assert last['five_day_pct']==pytest.approx(-6.187095588017247)
    assert last['twenty_day_pct']==pytest.approx(-9.677314974313488)
    assert all(r['twenty_day_pct'] is None for r in e['rows'][:20])
    assert all(r['from_twenty_close_high_pct'] is None for r in e['rows'][:19])


def test_rolling_high_and_volatility_are_not_full_future_or_full_sample_values():
    prices=[dict(date=str(i),close=100+i)for i in range(21)]
    r=derive(prices)
    assert r[-1]['twenty_day_pct']==20
    assert r[-1]['from_twenty_close_high_pct']==0
    assert r[-1]['twenty_day_realized_annualized_pct']>0
    prices.append(dict(date='21',close=60))
    out=derive(prices)
    assert out[:-1]==r
    assert out[-1]['from_twenty_close_high_pct']==-50
    prices[0]['close']=0
    with pytest.raises(ValueError,match='invalid close'):derive(prices)
