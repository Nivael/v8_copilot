import gzip
import json
from hashlib import sha256
import pytest
from canonical_json import digest
from st_regime_refresh import SourceCache, FIELDS, activity_fact
from st_regime_themes import build_themes, event_context


def test_resumption_and_intraday_halt_do_not_erase_real_trades():
    member={'symbol':'600001','trade_date':'2026-07-06','name':'ST测试'}
    quote={'close':9.5,'pre_close':10.,'vol':20.,'pct_chg':-5.}
    for events in ([{'suspend_type':'R'}],[{'suspend_type':'S','suspend_timing':'10:00-10:30'}]):
        assert activity_fact(member,quote,events,{})['suspension_status']=='trading'
    assert activity_fact(member,None,[{'suspend_type':'S','suspend_timing':''}],{})['suspension_status']=='suspended'
    assert activity_fact(member,None,[{'suspend_type':'R'}],{})['suspension_status']=='unknown'


def test_cached_response_integrity_and_cap_guard(tmp_path):
    cache=SourceCache(directory=tmp_path,token='test-not-real',url='http://example.invalid/')
    query={'api_name':'stock_st','params':{'trade_date':'20260706'},'fields':FIELDS['stock_st'],'url':cache.url}
    raw=json.dumps({'code':0,'data':{'fields':['ts_code'],'items':[['600001.SH']]}}).encode()
    h=sha256(raw).hexdigest();source=tmp_path/'responses'/(h+'.json.gz');source.write_bytes(gzip.compress(raw))
    ref={'query':query,'response_sha256':h}
    (tmp_path/'queries'/(digest(query)+'.json')).write_text(json.dumps(ref))
    assert cache.query('stock_st',query['params'])[0]==[{'ts_code':'600001.SH'}]
    source.write_bytes(gzip.compress(b'{}'))
    with pytest.raises(ValueError,match='changed'):cache.query('stock_st',query['params'])


def test_month_boundaries_compound_and_keep_partial_month():
    rows=[{'date':d,'return_pct':s,'market_pct':m,'small_cap_pct':m,'positive_pct':50} for d,s,m in [('2026-07-03',99,99),('2026-07-06',-10,-5),('2026-07-07',10,5),('2026-11-06',2,1)]]
    themes=build_themes({},rows)
    assert len(themes['months'])==2
    july,nov=themes['months']
    assert july['days']==2 and july['st_pct']==pytest.approx(-1)
    assert nov['days']==1 and nov['through']=='2026-11-06'
    assert all(r['date']!='2026-07-03' for r in themes['market_days'])


def test_date_only_event_excludes_disclosure_day_and_keeps_gaps():
    days=['2026-07-03','2026-07-06','2026-07-07','2026-07-08']
    inputs={'calendar':days,'fixed_prices':[{'symbol':'600001','trade_date':d,'close':c} for d,c in zip(days,[10,20,22,23],strict=True)]}
    daily=[{'date':d,'return_pct':1,'market_pct':2} for d in days[1:]]
    result=event_context({'published_on':'2026-07-06'},'600001',inputs,daily)
    assert result['not_earliest_reaction']
    assert result['windows']['1']['stock_pct']==pytest.approx(10)
    assert result['windows']['5']['stock_pct'] is None
    weekend=event_context({'published_on':'2026-07-05'},'600001',inputs,daily)
    assert weekend['anchor']=='2026-07-03'
    inputs['fixed_prices']=inputs['fixed_prices'][:1]
    assert event_context({'published_on':'2026-07-06'},'600001',inputs,daily)['windows']['1']['stock_pct'] is None


def test_announcement_packet_tampering_fails_closed():
    packet={'catalogs':{},'verified_events':[],'content_digest':'tampered'}
    with pytest.raises(ValueError,match='changed'):build_themes({'announcement_study':packet},[])


def test_frozen_fact_binding_deduplicates_questions_and_preserves_date_conflict():
    from st_regime_study_input import bind
    event={'id':'auction','title':'二拍再次流拍，公开日期有冲突','published_on':'2026-07-04','source':{'sha256':'file','page':4,'url':'https://example.com/file.pdf'}}
    question={'review':{'event_timeline':{'events':[event]}}}
    history={'details':{'002514.SZ':{'questions':[question,question]}}};history['content_digest']=digest(history)
    catalog={'through':'2026-11-06','endpoint_window_complete':True,'rows':[]};catalog['content_digest']=digest(catalog)
    result=bind({'through':'2026-11-06'},{'002514':catalog},history)
    events=result['announcement_study']['verified_events']
    assert len(events)==1 and events[0]['alternate_published_on']=='2026-07-06'
    catalog['through']='2026-09-03';catalog['content_digest']=digest({k:v for k,v in catalog.items() if k!='content_digest'})
    with pytest.raises(ValueError,match='window'):bind({'through':'2026-11-06'},{'002514':catalog},history)


def test_event_windows_do_not_turn_zero_volume_reference_snapshots_into_flat_returns():
    inputs={'calendar':['2026-09-03','2026-09-04'],'fixed_prices':[{'symbol':'000016','trade_date':'2026-09-03','close':2.46,'has_trade':True},{'symbol':'000016','trade_date':'2026-09-04','close':2.46,'has_trade':False}]}
    daily=[{'date':'2026-09-04','return_pct':1.,'market_pct':2.}]
    value=event_context({'published_on':'2026-09-03'},'000016',inputs,daily)['windows']['1']
    assert value['stock_pct'] is None and '停牌日参考值' in value['gap']
    assert value['market_pct']==pytest.approx(2.)


def test_same_announcement_episode_has_one_observation_with_two_preserved_views():
    from copy import deepcopy
    from st_regime_themes import coalesce_event_records
    base={'symbol':'002856','id':'investment','published_on':'2026-09-23','occurred_on':'2026-09-22','entity_scope':'issuer','change_kind':'progress','title':'签约','change':'已签约且保证金已缴','interpretation':'后续余款有条件','source':{'sha256':'same-source','page':38,'url':'https://example.com/a.pdf#page=38'}}
    pricing={**base,'title':'定价','change':'价格受协议约束','interpretation':'不等于二级市场保底','source':{**base['source'],'page':39,'url':'https://example.com/a.pdf#page=39'}}
    records=[base,pricing];frozen=deepcopy(records);result=coalesce_event_records(records)
    assert len(result)==1 and result[0]['source_record_count']==2 and len(result[0]['source_records'])==2
    assert '已签约且保证金已缴' in result[0]['change'] and '价格受协议约束' in result[0]['change']
    assert {r['source']['page'] for r in result[0]['source_records']}=={38,39} and records==frozen
    assert coalesce_event_records(list(reversed(records)))==result


@pytest.mark.parametrize('field,value',[('symbol','600363'),('published_on','2026-10-12'),('occurred_on','2026-09-23'),('entity_scope','subsidiary'),('change_kind','payment'),('report_period_end','2026-06-30'),('scheduled_for','2026-10-12'),('source','new-source')])
def test_different_subject_source_stage_or_time_is_not_coalesced(field,value):
    from st_regime_themes import coalesce_event_records
    base={'symbol':'002856','id':'investment','published_on':'2026-09-23','occurred_on':'2026-09-22','entity_scope':'issuer','change_kind':'progress','title':'签约','source':{'sha256':'old-source'}}
    other={**base,field:{'sha256':value} if field=='source' else value}
    result=coalesce_event_records([base,other]);assert len(result)==2 and len({r['event_key'] for r in result})==2


def test_exact_repeated_records_do_not_create_extra_views_or_observations():
    from st_regime_themes import coalesce_event_records
    r={'symbol':'002856','id':'investment','published_on':'2026-09-23','title':'签约','change':'已签约','source':{'sha256':'file'}}
    result=coalesce_event_records([r,r]);assert len(result)==1 and result[0]['source_record_count']==2 and len(result[0]['source_records'])==1
