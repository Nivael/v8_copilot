import json,copy,hashlib
from pathlib import Path
import pytest
from st_exit_observation import observe

def evidence():return json.loads((Path(__file__).resolve().parents[1]/'ST_EXIT_OBSERVATION_EVIDENCE_2026_11_21.json').read_text())
def test_real_replay_excludes_anchor_and_nontrading():
 e=evidence();assert observe(e['inputs']['sources'],e['inputs']['primary'])==e['reading']
 assert e['reading']['total_trading_stock_days']==44;assert e['reading']['one_price_stock_days']==0
 assert e['reading']['close_at_low_stock_days']==5;assert not e['reading']['executable_exit_verified']
def test_changed_bytes_and_primary_close_rejected():
 e=evidence();e['inputs']['sources'][0]['text']+=' '
 with pytest.raises(ValueError):observe(e['inputs']['sources'],e['inputs']['primary'])
 e=evidence();e['inputs']['primary']['603398.SH'][1]['raw_close']=1
 with pytest.raises(ValueError):observe(e['inputs']['sources'],e['inputs']['primary'])
def test_invalid_ohlc_even_after_rehash_rejected():
 e=evidence();s=e['inputs']['sources'][0];d=json.loads(s['text']);d['data']['sh603398']['day'][1][3]='0.1';s['text']=json.dumps(d);s['sha256']=hashlib.sha256(s['text'].encode()).hexdigest()
 with pytest.raises(ValueError):observe(e['inputs']['sources'],e['inputs']['primary'])
def test_missing_security_or_duplicate_source_rejected():
 e=evidence()
 with pytest.raises(ValueError):observe(e['inputs']['sources'][:-1],e['inputs']['primary'])
 with pytest.raises(ValueError):observe(e['inputs']['sources']+[e['inputs']['sources'][0]],e['inputs']['primary'])
