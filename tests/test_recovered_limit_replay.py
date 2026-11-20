from pathlib import Path
import copy
import json
import pytest
from recovered_limit_replay import replay

FOLDER=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limits/20261109-20261119')

def evidence():
    return json.loads(Path('RECOVERED_LIMIT_EVIDENCE_2026_11_21.json').read_text())


def test_saved_provider_limits_distinguish_close_at_low_from_limit_down():
    e=evidence();r=replay(e,FOLDER)
    assert r==e['reading']
    assert (r['limit_records'],r['trading_ohlc_pairs'])==(45,44)
    assert r['without_trading_ohlc']==[{'symbol':'688053','date':'2026-11-10'}]
    assert r['touch_down_limit_days']==r['close_at_down_limit_days']==2
    assert r['one_price_at_down_limit_days']==0
    assert {(r['symbol'],r['date'])for r in r['rows']if r['close_at_down_limit']}=={('603398','2026-11-19'),('002667','2026-11-09')}


def test_rejects_changed_source_request_and_missing_sessions():
    e=evidence();e['sources'][0]['params']['trade_date']='20261120'
    with pytest.raises(ValueError,match='request'):replay(e,FOLDER)
    e=evidence();e['sources'].pop()
    with pytest.raises(ValueError,match='nine'):replay(e,FOLDER)


def test_rejects_changed_original_bytes_and_ohlc_outside_limits(tmp_path):
    e=evidence();r=e['sources'][0];(tmp_path/(r['response_sha256']+'.json.gz')).write_bytes(b'bad')
    with pytest.raises((ValueError,OSError,EOFError)):replay(e,tmp_path)
    e=evidence();e['ohlc_reading']['companies'][0]['days'][0]['low']='0.01'
    with pytest.raises(ValueError,match='outside'):replay(e,FOLDER)
