from pathlib import Path
import json
import pytest
from szse_ohlc_field_review import analyze
FOLDER=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recent_breadth_history/sources/895130d3f8b80b5e2f8ef947dcb67a3d6a7c9bbe849b91dd2e3c7b62cda89f47/szse-history')
def data():return json.loads(Path('SZSE_OHLC_FIELD_EVIDENCE_2026_11_21.json').read_text())
def risk():return json.loads(Path('RISK_LIST_NOV20_EVIDENCE_2026_11_21.json').read_text())

def test_traded_single_price_up_is_not_a_limit_down_and_no_trade_is_not_single_price():
    e=data();r=analyze(e,FOLDER,risk());assert r==e['reading']
    assert (r['official_dated_mainboard_members'],r['trading'],r['nontrading'])==(74,72,2)
    assert (r['one_price_trading'],r['one_price_higher'],r['one_price_lower'])==(1,1,0)
    assert r['close_at_daily_low']==8 and r['actual_limit_columns']==[]
    same=[x for x in r['rows']if x.get('one_observed_price')];assert same[0]['symbol']=='000838.SZ'
    assert same[0]['close']=='1.32' and same[0]['reference']=='1.20'
    missing=[x for x in r['rows']if not x['is_trading']]
    assert {x['symbol']for x in missing}=={'002122.SZ','002717.SZ'}
    assert all('one_observed_price'not in x for x in missing)


def test_missing_columns_wrong_packet_and_changed_dated_roster_stop():
    e=data();e['reported_columns'].append('跌停价')
    with pytest.raises(ValueError,match='columns'):analyze(e,FOLDER,risk())
    e=data();e['szse_day_sha256']='0'*64
    with pytest.raises(ValueError,match='bytes'):analyze(e,FOLDER,risk())
    e=data();m=risk();m['reading']['target_day']='2026-11-19'
    with pytest.raises(ValueError,match='risk evidence'):analyze(e,FOLDER,m)
