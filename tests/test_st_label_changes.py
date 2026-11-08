from copy import deepcopy
from hashlib import sha256
import json
import pytest
from canonical_json import digest
from st_label_changes import label_scope_digest,label_change_view


def fixture():
    cal=['2026-07-03','2026-07-06','2026-07-07','2026-07-22','2026-07-23','2026-07-24','2026-07-30','2026-07-31','2026-08-03','2026-08-04','2026-11-06']
    specs=[('002731','ST萃华','*ST萃华','2026-07-07',None,'add_delisting_warning'),('000793','*ST华闻','ST华闻','2026-07-31',None,'remove_delisting_keep_other'),('600238','*ST椰岛','ST椰岛','2026-08-03',None,'remove_delisting_keep_other'),('603869','ST智知','XDST智知','2026-07-23','2026-07-24','ex_dividend_marker'),('600079','ST人福','XDST人福','2026-08-03','2026-08-04','ex_dividend_marker')]
    i={'calendar':cal,'through':cal[-1],'fixed_prices':[],'activities':[],'members':[]};rows=[]
    for symbol,before,after,effective,restore,kind in specs:
        for d in cal:i['members'].append({'symbol':symbol,'trade_date':d,'name':after if d>=effective and (not restore or d<restore) else before,'risk_type':'ST'})
        r={'symbol':symbol,'before_name':before,'effective_name':after,'effective_on':effective,'restore_on':restore,'kind':kind,'published_on':'2026-07-01','facts':[{'published_on':'2026-07-01','source':{'title':'正式安排','url':'https://example.com/a.pdf','page':1,'sha256':'a'*64}}]}
        if restore:r['dividend']={'cash_per_share':'.48' if symbol=='600079' else '.025','reference_cash_per_share':'.48' if symbol=='600079' else '.0237'}
        rows.append(r)
    raw={'603869':[('2026-07-22',7.44,7.68,1.5191),('2026-07-23',7.66,7.42,1.5232),('2026-07-24',7.7,7.66,1.5232)],'600079':[('2026-07-31',17.91,17.94,14.298),('2026-08-03',17.69,17.43,14.6917),('2026-08-04',17.55,17.69,14.6917)]};cache=[];sources=[]
    for symbol,quotes in raw.items():
        for d,c,prev,factor in quotes:
            cache += [{'api':'daily','date':d,'rows':[{'ts_code':symbol+'.SH','close':c,'pre_close':prev,'pct_chg':(c/prev-1)*100,'vol':100}]},{'api':'adj_factor','date':d,'rows':[{'ts_code':symbol+'.SH','adj_factor':factor}]}]
        for key in ('tencent_raw','tencent_qfq','eastmoney_raw','eastmoney_qfq'):
            values=[]
            for n,(d,c,prev,factor) in enumerate(quotes):
                value=c
                if key.endswith('qfq') and n==0:value=17.43 if symbol=='600079' else 7.416 if key.startswith('tencent') else 7.42
                values.append([d,'1',str(value),'20','1','100'])
            payload={'data':{'sh'+symbol:{'qt':{'sh'+symbol:['1','name',symbol]},'qfqday' if key.endswith('qfq') else 'day':values}}} if key.startswith('tencent') else {'data':{'code':symbol,'market':1,'klines':[','.join(v) for v in values]}}
            text=json.dumps(payload);sources.append({'symbol':symbol,'key':key,'raw_text':text,'sha256':sha256(text.encode()).hexdigest(),'url':'https://example.com/quote','observed_at':'2026-11-09T00:00:00Z'})
    p={'through':i['through'],'scope_digest':label_scope_digest(i),'rows':rows,'new_primary_sources':[{'pages':1}]*5,'quote_sources':sources,'cache_rows':cache,'identifier_rule':{}};p['content_digest']=digest(p);i['label_changes']=p
    daily=[{'date':d,'market_pct':-.5,'return_pct':2} for d in cal]
    return i,daily


def resign(i):
    p=i['label_changes'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})


def test_seven_name_boundaries_are_five_actions_without_membership_exits():
    i,d=fixture();before=deepcopy(i['members']);v=label_change_view(i,d)
    assert v['warning_changes']==3 and v['dividend_episodes']==2
    assert v['name_boundaries']==v['matching_boundaries']==7 and v['quote_points']==24
    assert all(r['same_st_presence_at_boundary'] for r in v['rows']) and i['members']==before


def test_ex_dividend_raw_fall_and_reference_rise_are_both_preserved():
    i,d=fixture();r=next(r for r in label_change_view(i,d)['rows'] if r['symbol']=='600079')['dividend_observation']
    assert r['raw_close_change_pct']<0<r['reference_price_change_pct'] and r['reference_matches_formula']
    assert r['calculated_cent_reference']==17.43 and r['previous_raw_close']==17.91 and r['ex_raw_close']==17.69


def test_differentiated_dividend_and_source_precision_are_not_flattened():
    i,d=fixture();r=next(r for r in label_change_view(i,d)['rows'] if r['symbol']=='603869')['dividend_observation']
    assert r['cash_per_eligible_share']==.025 and r['reference_cash_per_share']==.0237
    q={c['key']:c for c in r['channels']}
    assert q['tencent_qfq']['values'][0]['original_precision']=='7.416' and q['eastmoney_qfq']['values'][0]['original_precision']=='7.42'
    assert r['qfq_channel_return_spread_pp']==pytest.approx(.05568203956)


def test_future_facts_scope_and_raw_response_tampering_fail_closed():
    for change in ('future','scope','raw'):
        i,d=fixture()
        if change=='future':i['label_changes']['rows'][0]['facts'][0]['published_on']='2026-11-09';resign(i)
        elif change=='scope':i['members'][0]['name']='wrong'
        else:i['label_changes']['quote_sources'][0]['raw_text']+=' ';resign(i)
        with pytest.raises(ValueError):label_change_view(i,d)


def test_provider_name_conflict_is_shown_instead_of_rewriting_it():
    i,d=fixture();r=next(r for r in i['members'] if r['symbol']=='000793' and r['trade_date']=='2026-07-31');r['name']='*ST华闻';i['label_changes']['scope_digest']=label_scope_digest(i);resign(i)
    v=label_change_view(i,d);r=next(r for r in v['rows'] if r['symbol']=='000793');assert r['matching_boundaries']==0 and r['boundaries'][0]['observed_after']=='*ST华闻'


def test_xd_restoration_cannot_be_assigned_to_an_arbitrary_later_date():
    i,d=fixture();next(r for r in i['label_changes']['rows'] if r['symbol']=='603869')['restore_on']='2026-07-31';resign(i)
    with pytest.raises(ValueError,match='next market session'):label_change_view(i,d)
