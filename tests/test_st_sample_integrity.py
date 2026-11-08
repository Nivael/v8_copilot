from copy import deepcopy
import pytest
from canonical_json import digest
from st_sample_integrity import load_integrity, fixed_gap_note, price_scope_digest


def fixture():
    inputs={'calendar':['2026-07-03','2026-11-06'],'through':'2026-11-06','fixed_prices':[{'symbol':'002731','trade_date':'2026-11-06','close':.22}]}
    source={'url':'https://example.com/original.pdf#page=1','sha256':'a'*64,'page':1,'title':'公司原公告'}
    case={'symbol':'002731','as_of':inputs['through'],'classification':'anchor_suspended','title':'缺的是起点','explanation':'起点停牌，期末仍在交易','boundary':'不改用更早日期','anchor':{'date':'2026-07-03','close':None},'endpoint':{'date':inputs['through'],'close':.22},'facts':[{'published_on':'2026-11-06','text':'仍在整理期','source':source}]}
    packet={'through':inputs['through'],'price_scope_digest':price_scope_digest(inputs),'cases':[case]};packet['content_digest']=digest(packet)
    inputs['sample_integrity']=packet
    return inputs


def resign(inputs):
    packet=inputs['sample_integrity'];packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})


def test_gap_explanation_preserves_missing_anchor_and_does_not_leak_to_earlier_windows():
    inputs=fixture();packet=load_integrity(inputs)
    note=fixed_gap_note(packet,'002731','2026-07-03','2026-11-06')
    assert note['classification']=='anchor_suspended'
    assert fixed_gap_note(packet,'002731','2026-07-03','2026-08-28') is None
    assert fixed_gap_note(packet,'000016','2026-07-03','2026-11-06') is None
    assert inputs['fixed_prices']==[{'symbol':'002731','trade_date':'2026-11-06','close':.22}]


def test_case_content_and_price_scope_are_both_bound():
    inputs=fixture();inputs['sample_integrity']['cases'][0]['explanation']='invented'
    with pytest.raises(ValueError,match='packet changed'):load_integrity(inputs)
    inputs=fixture();inputs['fixed_prices'].append({'symbol':'002731','trade_date':'2026-07-03','close':4.35})
    with pytest.raises(ValueError,match='price/window'):load_integrity(inputs)
    inputs['sample_integrity']['price_scope_digest']=price_scope_digest(inputs);resign(inputs)
    with pytest.raises(ValueError,match='endpoint changed'):load_integrity(inputs)


def test_incomplete_sources_future_facts_and_conflicting_classification_fail_closed():
    for alteration in ('future','source','classification','duplicate'):
        inputs=fixture();case=inputs['sample_integrity']['cases'][0]
        if alteration=='future':case['facts'][0]['published_on']='2026-11-10'
        elif alteration=='source':case['facts'][0]['source']['page']=None
        elif alteration=='classification':case['classification']='endpoint_delisted'
        else:inputs['sample_integrity']['cases'].append(deepcopy(case))
        resign(inputs)
        with pytest.raises(ValueError):load_integrity(inputs)
