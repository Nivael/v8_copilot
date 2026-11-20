from pathlib import Path
from hashlib import sha256
import json
import pytest
from st_fixed_nov20 import analyze
FOLDER=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recent_breadth_history/sources/895130d3f8b80b5e2f8ef947dcb67a3d6a7c9bbe849b91dd2e3c7b62cda89f47/szse-history')
def evidence():return json.loads(Path('ST_FIXED_NOV20_EVIDENCE_2026_11_21.json').read_text())

def test_two_actual_trade_endpoints_keep_four_missing_or_nontrading_securities():
    e=evidence();r=analyze(e,FOLDER);assert r==e['reading']
    assert (r['fixed_members'],r['paired'],r['advancing'],r['declining'],r['flat'])==(150,146,24,115,7)
    assert r['declining_at_least_5pct']==24
    assert r['equal_weight_one_day_pct']==pytest.approx(-2.379803606754907)
    assert r['median_one_day_pct']==pytest.approx(-2.596296296296296)
    assert {x['symbol']:x['status']for x in r['rows']if x['status']!='paired'}=={'000016.SZ':'missing_quote20','002122.SZ':'nontrading20','002717.SZ':'nontrading20','002731.SZ':'missing_quote20'}
    assert all('change_pct'not in x for x in r['rows']if x['status']!='paired')


def test_reference_change_is_preserved_and_excluded_from_close_to_close_distribution():
    e=evidence();s=e['sse_sources'][0];p=json.loads(s['text']);row=next(x for x in p['kline']if x[0]==20261120);row[2]=float(row[2])+0.01;s['text']=json.dumps(p);raw=s['text'].encode();s.update(sha256=sha256(raw).hexdigest(),bytes=len(raw))
    r=analyze(e,FOLDER);x=next(x for x in r['rows']if x['symbol']==s['code']+'.SH')
    assert x['status']=='reference_mismatch'and'change_pct'not in x
    assert r['paired']==145


def test_rejects_source_drift_incomplete_scope_and_wrong_benchmark_window():
    e=evidence();e['szse_day_refs'][0]['sha256']='0'*64
    with pytest.raises(ValueError,match='packet bytes'):analyze(e,FOLDER)
    e=evidence();e['sse_sources'].pop()
    with pytest.raises(ValueError,match='all fixed SSE'):analyze(e,FOLDER)
    e=evidence();e['benchmark_points'][0]['trade_date']='2026-11-18'
    with pytest.raises(ValueError,match='same-day'):analyze(e,FOLDER)
