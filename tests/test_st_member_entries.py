from copy import deepcopy
import pytest
from canonical_json import digest
from st_member_entries import member_entry_view, entry_observation, entry_price_scope_digest
from st_member_transitions import membership_scope_digest

def fixture():
    days=['2026-07-%02d'%d for d in (3,6,7,8,9,10,13,14)]
    i={'calendar':days,'through':days[-1],'members':[{'symbol':'000972','trade_date':d} for d in days[2:]],'fixed_prices':[{'symbol':'000972','trade_date':d,'close':10+n,'has_trade':True} for n,d in enumerate(days)],'benchmarks':[],'activities':[]}
    r={'symbol':'000972','suspend_on':days[1],'effective_on':days[2],'announced_on':days[1],'first_provider_st':days[2],'warning_type':'delisting','cause_key':'reorganization_accepted','facts':[{'published_on':days[1],'source':{'sha256':'a'*64,'url':'https://example.com/a.pdf','page':1,'title':'正式受理'}}]}
    packet={'anchor':days[0],'through':i['through'],'membership_scope_digest':membership_scope_digest(i),'price_scope_digest':entry_price_scope_digest(i),'rows':[r]};packet['content_digest']=digest(packet);i['member_entries']=packet
    daily=[{'date':d,'market_pct':1,'return_pct':-1} for d in days[1:]]
    return i,daily

def resign(i):
    p=i['member_entries'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})

def test_common_anchor_includes_halt_and_does_not_invent_full_twenty_days():
    i,d=fixture();v=member_entry_view(i,d);r=v['rows'][0];w=r['observation']['windows']
    assert r['observation']['anchor']=='2026-07-03'
    assert w['5']['through']=='2026-07-13' and w['5']['market_days']==6
    assert w['5']['stock_pct']==pytest.approx(60)
    assert w['5']['market_pct']==pytest.approx((1.01**6-1)*100)
    assert w['20']['stock_pct'] is None and w['20']['market_pct'] is None
    assert w['through']['stock_pct']==pytest.approx(70)
    assert v['composition']=={'initial':0,'entered':1,'left':0,'endpoint':1}

def test_nontraded_endpoint_and_missing_benchmark_day_never_become_zero():
    i,d=fixture();r=i['member_entries']['rows'][0];i['fixed_prices'][0]['has_trade']=False
    assert entry_observation(r,i,d)['windows']['5']['stock_pct'] is None
    assert entry_observation(r,i,d[:-2])['windows']['5']['market_pct'] is None

def test_corrupt_scope_future_source_unknown_cause_and_duplicate_fail_closed():
    for mutation in ('price','packet','future','cause','duplicate'):
        i,d=fixture();r=i['member_entries']['rows'][0]
        if mutation=='price':i['fixed_prices'][0]['close']=20
        elif mutation=='packet':r['cause_key']='changed'
        elif mutation=='future':r['facts'][0]['published_on']='2026-11-07';resign(i)
        elif mutation=='cause':r['cause_key']='all_risks_gone';resign(i)
        else:i['member_entries']['rows'].append(deepcopy(r));resign(i)
        with pytest.raises(ValueError):member_entry_view(i,d)

def test_membership_disagreement_is_visible_instead_of_rewriting_source():
    i,d=fixture();i['member_entries']['rows'][0]['effective_on']='2026-07-08';resign(i)
    v=member_entry_view(i,d)
    assert v['matching_boundaries']==0 and not v['rows'][0]['effective_matches_membership']
