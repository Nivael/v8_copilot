from copy import deepcopy
from hashlib import sha256
import json
import pytest
from canonical_json import digest
from st_index_crosscheck import benchmark_scope_digest, crosscheck_view,parse_quotes


def fixture():
    calendar=['2026-07-02','2026-07-03','2026-07-06','2026-07-07']
    inputs={'calendar':calendar,'through':calendar[-1],'benchmarks':[]}
    sources=[]
    for code,name,key in [('000985','中证全指','csi_all_share'),('932000','中证2000','csi_2000')]:
        closes=[100,100.0045,99,98]
        inputs['benchmarks'] += [{'benchmark_id':key,'trade_date':d,'close':v} for d,v in zip(calendar,closes)]
        raw=json.dumps({'data':{'code':code,'name':name,'market':1 if code=='000985' else 2,'klines':[f'{d},100,{v},100,98' for d,v in zip(calendar,[100,100.01,99,98])]}})
        sources.append({'symbol':code,'vendor':'eastmoney','raw_text':raw,'sha256':sha256(raw.encode()).hexdigest(),'observed_at':'2026-11-09T00:00:00Z','url':'https://push2his.eastmoney.com/example'})
    packet={'benchmark_scope_digest':benchmark_scope_digest(inputs),'sources':sources,'empty_routes':[],'identity_sources':[]};packet['content_digest']=digest(packet);inputs['index_crosscheck']=packet
    daily=[{'date':d,'return_pct':-.5} for d in calendar[1:]]
    return inputs,daily


def resign(i):
    p=i['index_crosscheck'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})


def raw_mutation(i,mutate):
    s=i['index_crosscheck']['sources'][0];raw=json.loads(s['raw_text']);mutate(raw['data']);s['raw_text']=json.dumps(raw);s['sha256']=sha256(s['raw_text'].encode()).hexdigest();resign(i)


def test_precision_conflicts_are_preserved_and_never_correct_base_prices():
    i,d=fixture();old=deepcopy(i['benchmarks']);v=crosscheck_view(i,d)
    assert i['benchmarks']==old and v['unique_index_dates']==8 and v['quote_points']==8
    assert v['precision_difference_count']==2
    r=v['rows'][0];assert r['rounding_agree_points']==3
    assert r['precision_differences'][0]['difference_points']==pytest.approx(.0055)
    assert r['windows'][1]['anchor']=='2026-07-03' and r['windows'][1]['days']==2
    assert r['windows'][1]['checked_pct']==pytest.approx((98/100.01-1)*100)


def test_raw_source_and_scope_tampering_are_rejected():
    i,d=fixture();i['index_crosscheck']['sources'][0]['raw_text']+=' ';resign(i)
    with pytest.raises(ValueError,match='raw source digest'):crosscheck_view(i,d)
    i,d=fixture();i['benchmarks'][0]['close']=101
    with pytest.raises(ValueError,match='scope changed'):crosscheck_view(i,d)


@pytest.mark.parametrize('change',['identity','duplicate_day','missing_day','duplicate_channel','missing_index'])
def test_identity_and_coverage_are_not_inferred_from_http_success(change):
    i,d=fixture()
    if change=='identity':raw_mutation(i,lambda x:x.update(name='wrong index'))
    elif change=='duplicate_day':raw_mutation(i,lambda x:x['klines'].append(x['klines'][0]))
    elif change=='missing_day':raw_mutation(i,lambda x:x['klines'].pop())
    elif change=='duplicate_channel':i['index_crosscheck']['sources'].append(deepcopy(i['index_crosscheck']['sources'][0]));resign(i)
    else:i['index_crosscheck']['sources'].pop();resign(i)
    with pytest.raises(ValueError):crosscheck_view(i,d)


def test_small_price_differences_can_change_zero_or_stress_classification_and_are_flagged():
    i,d=fixture();raw_mutation(i,lambda x:x['klines'].__setitem__(1,'2026-07-03,100,100,100,98'))
    r=crosscheck_view(i,d)['rows'][0]
    assert r['environment_boundary_changes'][0]['date']=='2026-07-03'
