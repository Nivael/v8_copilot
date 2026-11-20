from pathlib import Path
from hashlib import sha256
import json
import pytest
from st_case_ohlc_crosscheck import crosscheck
FOLDER=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119')
def evidence():return json.loads(Path('ST_CASE_OHLC_CROSSCHECK_EVIDENCE_2026_11_21.json').read_text())

def test_ohlc_and_official_close_controls_remain_distinct_and_new_days_diverge():
    e=evidence();r=crosscheck(e,FOLDER);assert r==e['reading']
    assert sum(x['matched_ohlc_values']for x in r['cases'])==108
    assert sum(x['sse_close_control_days']for x in r['cases'])==30
    assert [x['new_day']['close_vs_previous']for x in r['cases']]==['lower','higher','lower']
    assert all(not x['new_day']['one_observed_price']and x['new_day']['actual_down_limit']is None for x in r['cases'])
    assert [x['one_price_dates']for x in r['cases']]==[[],['2026-11-18'],['2026-11-18']]


def rehash(src,p):
    src['text']=json.dumps(p);raw=src['text'].encode();src.update(sha256=sha256(raw).hexdigest(),bytes=len(raw))


def test_rejects_byte_change_raw_ohlc_conflict_and_official_close_conflict():
    e=evidence();e['raw_ohlc_sources'][0]['text']+=' '
    with pytest.raises(ValueError,match='bytes'):crosscheck(e,FOLDER)
    e=evidence();s=e['raw_ohlc_sources'][0];p=json.loads(s['text']);next(r for r in p['data']['sh600180']['day']if r[0]=='2026-11-19')[1]='0.620';rehash(s,p)
    with pytest.raises(ValueError,match='OHLC conflict'):crosscheck(e,FOLDER)
    e=evidence();s=e['sse_close_sources'][0];p=json.loads(s['text']);next(r for r in p['kline']if r[0]==20261120)[1]=0.56;rehash(s,p)
    with pytest.raises(ValueError,match='SSE close conflict'):crosscheck(e,FOLDER)


def test_rejects_missing_subject_and_adjusted_instead_of_raw():
    e=evidence();e['sse_close_sources'].pop()
    with pytest.raises(ValueError,match='three'):crosscheck(e,FOLDER)
    e=evidence();s=e['raw_ohlc_sources'][0];p=json.loads(s['text']);b=p['data']['sh600180'];b['qfqday']=b.pop('day');rehash(s,p)
    with pytest.raises(ValueError,match='unadjusted'):crosscheck(e,FOLDER)
