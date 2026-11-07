from datetime import date,timedelta
from hashlib import sha256
import json

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from trader_swing_reading import price_observation,packet
from trader_research_notes import attach_swing_notes,reviewed_packet


def sample(values=None):
    values=values or [100]*5+[95,90,85,80,75]+[70]*10+[69,69,70,71,72]
    days=[(date(2026,9,1)+timedelta(days=i)).isoformat() for i in range(len(values))]
    points={day:{'close':value,'previous_close':values[max(0,i-1)],'is_trading':True} for i,(day,value) in enumerate(zip(days,values,strict=True))}
    last={'last':values[-1],'prev_close':values[-2],'pct_chg':(values[-1]/values[-2]-1)*100,'amount':20_000_000,'is_trading':True}
    return days,points,last


def test_explicit_watchlist_survives_pool_removal_and_uses_exchange_security_names():
    from trader_swing_reading import watched_members
    result=watched_members({'688053.SH':{'security_name':'思科瑞'},'603398.SH':{'security_name':'*ST沐邦'}})
    assert len(result)==4
    assert next(r for r in result if r['ts_code']=='688053.SH')['name']=='思科瑞'
    assert next(r for r in result if r['ts_code']=='603398.SH')['name']=='*ST沐邦'
    assert all(r['name']!=r['ts_code'] for r in result)


def test_initial_repair_needs_decline_repair_and_liquidity_without_invented_score():
    days,points,last=sample();result=price_observation('688629.SH','样本',days,points,last)
    assert result['stage']=='early_repair' and result['oversold']
    assert result['twenty_day_change_pct']==pytest.approx(-28)
    assert result['five_day_change_pct']==pytest.approx((72/70-1)*100)
    assert result['five_day_mean_close']==pytest.approx(70.2)
    last['amount']=100
    assert price_observation('688629.SH','样本',days,points,last)['stage']=='liquidity_insufficient'


def test_recent_fast_rebound_and_falling_price_are_not_initial_repair():
    days,points,last=sample([100]*5+[95,90,85,80,75]+[60]*10+[61,65,70,75,80])
    result=price_observation('a','样本',days,points,last)
    assert result['oversold'] and result['stage']=='rebounded_far'
    days,points,last=sample([100]*5+[95,90,85,80,75]+[70]*10+[69,68,67,66,65])
    assert price_observation('a','样本',days,points,last)['stage']=='still_weak'


def test_known_suspension_is_a_gap_and_an_inactive_window_baseline_has_no_return():
    days,points,last=sample();points[days[4]]={'close':None,'previous_close':None,'is_trading':False}
    result=price_observation('a','样本',days,points,last)
    assert result['path'][4]['level'] is None and result['nontrading_days']==1
    assert result['twenty_day_change_pct'] is None and not result['oversold']
    del points[days[10]]
    assert price_observation('a','样本',days,points,last)['availability']=='history_incomplete'
    last['is_trading']=False
    assert price_observation('a','样本',days,points,last)['availability']=='not_trading'


def test_price_returns_use_official_previous_close_rather_than_unadjusted_price_ratio():
    days,points,last=sample();points[days[10]]['previous_close']=150
    result=price_observation('a','样本',days,points,last)
    assert result['path'][-1]['level']==pytest.approx(36)
    assert result['twenty_day_change_pct']==pytest.approx(-64)


def test_content_changed_packet_is_rejected(tmp_path):
    value={'data':{'a':1}};value['content_digest']=digest(value);path=tmp_path/'source.json';atomic_write_json(path,value)
    assert packet(path)==value
    value['data']['a']=2;atomic_write_json(path,value)
    with pytest.raises(ValueError,match='changed'):packet(path)


def test_closed_source_needs_exact_query_and_raw_bytes_even_after_projection_is_redigested(tmp_path):
    from trader_swing_reading import closing_day
    from market_breadth_refresh import parse_sse
    from market_breadth import SSE_SELECT
    day='2026-11-04';directory=tmp_path/'trader_observations'/day/'closing_breadth';(directory/'responses').mkdir(parents=True)
    payload={'date':20261104,'time':162904,'total':1,'begin':0,'end':1,'list':[['600000','样本',9,10,-10,100,100000,'E110','ASH','']]}
    raw=json.dumps(payload).encode();key=sha256(raw).hexdigest();(directory/'responses'/(key+'.json')).write_bytes(raw)
    ref={'url':'https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/equity','params':{'select':SSE_SELECT,'begin':0,'end':500},'response_sha256':key,'bytes':len(raw),'observed_at':'2026-11-05T00:00:00Z'}
    value={'version':'trader_single_venue_close_v1','venue':'SSE','through':day,'observed_at':'2026-11-05T01:00:00Z','responses':[ref],'block':parse_sse([payload],day)}
    value['content_digest']=digest(value);atomic_write_json(directory/'sse_close.json',value)
    assert closing_day(tmp_path,day,'SSE')[0]['600000.SH']['last']==9
    ref['params']['begin']=500;value['content_digest']=digest({k:v for k,v in value.items() if k!='content_digest'});atomic_write_json(directory/'sse_close.json',value)
    with pytest.raises(ValueError,match='scope'):closing_day(tmp_path,day,'SSE')
    ref['params']['begin']=0;value['content_digest']=digest({k:v for k,v in value.items() if k!='content_digest'});atomic_write_json(directory/'sse_close.json',value)
    (directory/'responses'/(key+'.json')).write_bytes(raw+b' ')
    with pytest.raises(ValueError,match='source changed'):closing_day(tmp_path,day,'SSE')


def test_review_is_withdrawn_on_new_prices_changed_original_or_unbound_citation(tmp_path):
    directory=tmp_path/'company_updates/documents';directory.mkdir(parents=True)
    raw=b'%PDF-test';key=sha256(raw).hexdigest();(directory/(key+'.pdf')).write_bytes(raw)
    text='公开事实';url='https://static.cninfo.com.cn/finalpage/2026-10-29/123.PDF'
    document={'announcement_id':'123','code':'688629','url':url,'response_url':url,'raw_sha256':key,'bytes':len(raw),'pages':[text],
              'existing_local_body_id_match':False,'existing_local_text_match':False}
    atomic_write_json(directory/'123.json',document)
    note={'judgment':'等待确认','reasons':['已核公告'],'watch_next':['后续披露'],'sources':[{'label':'原公告','url':url}]}
    value={'version':'trader_research_notes_v1','checked_at':'2026-11-05T16:00:00Z','basis_digest':'prices',
           'sources':[{'kind':'company_pdf','announcement_id':'123','code':'688629','url':url,'raw_sha256':key,'pages':[{'page':1,'text_sha256':sha256(text.encode()).hexdigest()}]}],
           'data':{'analysis':{'headline':'等待确认'},'notes':{'688629.SH':note}}}
    value['content_digest']=digest(value);path=tmp_path/'swing_watch/research.json';atomic_write_json(path,value)
    data={'groups':[{'rows':[{'symbol':'688629.SH'}]}],'watchlist':[{'symbol':'688629.SH'}]}
    assert attach_swing_notes(data,'prices',tmp_path)['watchlist'][0]['note']==note
    assert 'note' not in data['watchlist'][0]
    assert 'analysis' not in attach_swing_notes(data,'new prices',tmp_path)
    (directory/(key+'.pdf')).write_bytes(b'changed')
    assert 'analysis' not in attach_swing_notes(data,'prices',tmp_path)
    (directory/(key+'.pdf')).write_bytes(raw)
    value['data']['notes']['688629.SH']['sources'][0]['url']='https://example.com/unreviewed'
    value['content_digest']=digest({k:v for k,v in value.items() if k!='content_digest'});atomic_write_json(path,value)
    with pytest.raises(ValueError,match='citation'):reviewed_packet(path,tmp_path,basis='prices')
