from pathlib import Path
from hashlib import sha256
import gzip
import json
import shutil
import pytest
from st_limit_cohort_replay import replay

FOLDER=Path('/Volumes/Leibniz/dev/st_research/local_data/v8_copilot/market_risk/recovered_limit_cohorts/20261109-20261119')
def manifest():return json.loads(Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json').read_text())['manifest']

def test_both_cohorts_keep_nonobserved_days_and_different_denominators():
    e=json.loads(Path('ST_LIMIT_COHORT_EVIDENCE_2026_11_21.json').read_text());r=replay(e['manifest'],FOLDER)
    assert r==e['reading'];daily,fixed=r['groups']
    assert sum(d['paired']for d in daily['days'])==1269
    assert sum(d['paired']for d in fixed['days'])==1327
    assert daily['days'][-1]['close_at_down']==5 and fixed['days'][-1]['close_at_down']==7
    assert [d['one_price_down']for d in daily['days']]==[0]*7+[3,1]
    assert {x['symbol']for x in fixed['rows']if x['status']=='missing_daily'}=={'000016.SZ','002717.SZ','002731.SZ'}
    assert all('close_at_down'not in x for x in fixed['rows']if x['status']=='missing_daily')
    assert all(d['unresolved_trading']==0 for d in daily['days']+fixed['days'])


def test_missing_limit_stays_unknown_instead_of_false(tmp_path):
    m=manifest()
    for p in FOLDER.glob('*.json.gz'):shutil.copyfile(p,tmp_path/p.name)
    ref=next(s for s in m['sources']if s['api_name']=='stk_limit'and s['params']['trade_date']=='20261119')
    raw=gzip.decompress((tmp_path/(ref['response_sha256']+'.json.gz')).read_bytes());p=json.loads(raw)
    p['data']['items']=[r for r in p['data']['items']if r[1]!='603398.SH']
    new=json.dumps(p).encode();ref['response_sha256']=sha256(new).hexdigest();ref['bytes']=len(new)
    (tmp_path/(ref['response_sha256']+'.json.gz')).write_bytes(gzip.compress(new))
    r=replay(m,tmp_path);row=next(x for x in r['groups'][0]['rows']if x['symbol']=='603398.SH'and x['date']=='2026-11-19')
    assert row['status']=='missing_limit' and 'close_at_down'not in row
    last=r['groups'][0]['days'][-1];assert last['paired']==140 and last['unresolved_trading']==1


def test_rejects_missing_day_query_drift_and_changed_fixed_scope():
    m=manifest();m['sources'].pop()
    with pytest.raises(ValueError,match='27'):replay(m,FOLDER)
    m=manifest();m['sources'][0]['params']['trade_date']='20261120'
    with pytest.raises(ValueError,match='request'):replay(m,FOLDER)
    m=manifest();m['fixed_symbols'][0]=m['fixed_symbols'][1]
    with pytest.raises(ValueError,match='150'):replay(m,FOLDER)
