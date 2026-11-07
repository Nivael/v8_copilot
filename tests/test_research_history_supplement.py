from copy import deepcopy
from hashlib import sha256
import json
from urllib.parse import urlencode

import pytest

from data_refresh import atomic_write_json
from research_history_prices import stock_path,supplemental_history


def test_unknown_early_gap_cannot_be_flattened_across_the_official_hand_off():
    days=['2026-09-02','2026-09-03','2026-09-04']
    old={days[0]:{'close':10,'volume':100}}
    official={days[-1]:{'close':9,'previous_close':10,'is_trading':True}}
    assert stock_path(days,old,official)[-1]['level'] is None
    old[days[1]]={'close':None,'volume':0}  # An explicitly observed full-day suspension.
    assert stock_path(days,old,official)[-1]['level']==90
    old[days[1]]={'close':8,'volume':100}
    assert stock_path(days,old,official)[-1]['level']==72


def fixture(root):
    calendar=['2026-09-02','2026-09-03','2026-09-04']
    historical={calendar[0]:{'close':10,'volume':100}}
    official={calendar[-1]:{'close':9,'previous_close':8,'is_trading':True}}
    data={'code':0,'data':{'sz000001':{'qt':{'sz000001':['51','样本公司','000001']},'qfqday':[
        [calendar[0],'10','10','11','9','100'],[calendar[1],'8','8','9','7','100'],[calendar[2],'9','9','10','8','100']]}}}
    url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'sz000001,day,{calendar[0]},{calendar[-1]},640,qfq'})
    ref={'url':url,'response_url':url,'observed_at':'2026-09-05T00:00:00Z','through':calendar[-1]}
    return calendar,historical,official,data,ref


def write(root,data,ref):
    folder=root/'inputs/tencent_qfq';folder.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(data).encode();ref={**ref,'sha256':sha256(raw).hexdigest(),'bytes':len(raw)}
    (folder/(ref['sha256']+'.json')).write_bytes(raw);atomic_write_json(folder/'000001.json',ref)
    return folder,ref


def test_complete_qfq_window_recovers_missing_early_prices_and_uses_official_returns(tmp_path):
    days,old,official,data,ref=fixture(tmp_path);original=deepcopy(old)
    folder,ref=write(tmp_path,data,ref)
    history,source=supplemental_history(tmp_path,'000001.SZ',days,old,official)
    assert old==original and source==ref and len(history)==2
    assert stock_path(days,history,official)[-1]['level']==90
    assert supplemental_history(tmp_path,'000002.SZ',days,old,official)==(old,None)
    (folder/(ref['sha256']+'.json')).write_bytes(b'{}')
    with pytest.raises(ValueError,match='original changed'):supplemental_history(tmp_path,'000001.SZ',days,old,official)


@pytest.mark.parametrize('change',['identity','url','duplicate','order','nonfinite','ohlc','volume','start','end','handoff','official','adjustment','future','naive','missing_qfq'])
def test_rehashed_supplement_cannot_change_identity_calendar_adjustment_or_endpoint(tmp_path,change):
    days,old,official,data,ref=fixture(tmp_path);block=data['data']['sz000001'];rows=block['qfqday']
    if change=='identity':block['qt']['sz000001'][2]='000002'
    elif change=='url':ref['url']=ref['url'].replace('qfq','hfq');ref['response_url']=ref['url']
    elif change=='duplicate':rows.insert(1,rows[0])
    elif change=='order':rows.reverse()
    elif change=='nonfinite':rows[1][2]='NaN'
    elif change=='ohlc':rows[1][3]='1'
    elif change=='volume':rows[1][-1]='0'
    elif change=='start':rows.pop(0)
    elif change=='end':rows.pop()
    elif change=='handoff':rows.pop(1)
    elif change=='official':official[days[-1]]['close']=90
    elif change=='adjustment':old[days[0]]['close']=11
    elif change=='future':ref['observed_at']='2099-01-01T00:00:00Z'
    elif change=='naive':ref['observed_at']='2026-09-05T00:00:00'
    else:block['day']=block.pop('qfqday')
    write(tmp_path,data,ref)
    with pytest.raises(ValueError):supplemental_history(tmp_path,'000001.SZ',days,old,official)


def test_different_early_basis_requires_explicit_review_and_many_matching_official_returns(tmp_path):
    from datetime import date
    from market_calendar import sessions_2026
    days,old,official,data,ref=fixture(tmp_path)
    days=sessions_2026(date(2026,9,2),date(2026,11,5));ref.update(through=days[-1],observed_at='2026-11-05T16:00:00Z')
    ref['url']='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'sz000001,day,{days[0]},{days[-1]},640,qfq'});ref['response_url']=ref['url']
    data['data']['sz000001']['qfqday']=[[day,'10','10','11','9','100'] for day in days]
    official={day:{'close':10,'previous_close':10,'is_trading':True} for day in days if day>='2026-09-04'}
    old[days[0]]['close']=11;write(tmp_path,data,ref)
    with pytest.raises(ValueError,match='reviewed replacement'):supplemental_history(tmp_path,'000001.SZ',days,old,official)
    ref.update(historical_basis_replaced=True,basis_review_note='旧段与完整源不同，核查整段替换。');write(tmp_path,data,ref)
    assert supplemental_history(tmp_path,'000001.SZ',days,old,official)[0][days[0]]['close']==10
    official[days[-1]]['previous_close']=11
    with pytest.raises(ValueError,match='official return'):supplemental_history(tmp_path,'000001.SZ',days,old,official)
