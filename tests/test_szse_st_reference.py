from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from canonical_json import digest
import szse_st_reference as m

NOW=datetime(2026,11,5,5,tzinfo=timezone.utc)


def row(code,name,change=0,active=True):
    return {'ts_code':code+'.SZ','security_name':name,'is_trading':active,'last':10*(1+change/100),'prev_close':10}


@pytest.fixture
def inputs(monkeypatch):
    monkeypatch.setitem(m.PLAN,'start','2026-09-04');monkeypatch.setitem(m.PLAN,'through','2026-09-08')
    events=[{'symbol':'000002','effective_on':'2026-09-07','old_name':'ST乙','new_name':'乙退','kind':'delisting_period'},
            {'symbol':'000003','effective_on':'2026-09-07','old_name':'丙','new_name':'ST丙','kind':'warning_added'},
            {'symbol':'000001','effective_on':'2026-09-08','old_name':'ST甲','new_name':None,'kind':'listing_end'}]
    return {'anchor':[{'ts_code':'000001.SZ','name':'ST甲'},{'ts_code':'000002.SZ','name':'ST乙'}],'proofs':events,
            'days':[{'date':'2026-09-04','source_marked':['000001.SZ','000002.SZ'],'rows':[row('000001','ST甲',10),row('000002','ST乙',-10),row('000003','丙')]},
                    {'date':'2026-09-07','source_marked':['000001.SZ','000003.SZ'],'rows':[row('000001','ST甲',20),row('000002','乙退',-90),row('000003','ST丙')]},
                    {'date':'2026-09-08','source_marked':['000003.SZ'],'rows':[row('000002','乙退'),row('000003','ST丙',-10)]}],
            'endpoint_members':['000003.SZ'],'endpoint_list_observed_on':'2026-09-09',
            'history_fetched_at':'2026-11-05T04:00:00+00:00','history_materialized_at':'2026-11-05T04:01:00+00:00'}


def test_all_effective_changes_and_non_survivors_define_the_reference(inputs):
    data=m.project(inputs)
    assert data['availability']=='observed' and [p['close'] for p in data['points']]==pytest.approx([1000,1100,990])
    assert data['return_pct']==pytest.approx(-1) and data['max_drawdown_pct']==pytest.approx(-10)
    assert data['distinct_members']==3 and data['anchor_members']==2 and data['endpoint_members']==1
    assert data['reviewed_transitions']==3 and data['member_day_observations']==5
    assert data['combined_ST_ready'] is data['historical_PIT'] is data['portfolio_wealth'] is data['effect_measured'] is False
    assert [p['member_count'] for p in data['points']]==[2,2,1]
    # A departing stock's -90% is neither silently included nor converted into a zero payoff.
    assert data['points'][1]['daily_return_pct']==pytest.approx(10)


@pytest.mark.parametrize('bad',['missing_event','extra_event','wrong_old','wrong_new','wrong_kind','duplicate_event','endpoint',
    'first_day','calendar','duplicate_price','wrong_effective_day'])
def test_unexplained_or_rebound_membership_changes_cannot_publish_a_path(inputs,bad):
    if bad=='missing_event':inputs['proofs'].pop(0)
    elif bad=='extra_event':inputs['proofs'].append({'symbol':'000099','effective_on':'2026-09-07','old_name':'某公司','new_name':'ST某公司','kind':'warning_added'})
    elif bad=='wrong_old':inputs['proofs'][0]['old_name']='ST其他'
    elif bad=='wrong_new':inputs['proofs'][0]['new_name']='其他退'
    elif bad=='wrong_kind':inputs['proofs'][1]['kind']='warning_removed'
    elif bad=='duplicate_event':inputs['proofs'].append(dict(inputs['proofs'][0]))
    elif bad=='endpoint':inputs['endpoint_members'].append('000002.SZ')
    elif bad=='first_day':inputs['days'][0]['source_marked'].append('000099.SZ')
    elif bad=='calendar':inputs['days'][1]['date']='2026-09-04'
    elif bad=='duplicate_price':inputs['days'][0]['rows'].append(dict(inputs['days'][0]['rows'][0]))
    else:inputs['proofs'][0]['effective_on']='2026-09-08'
    with pytest.raises(ValueError):m.project(inputs)


def test_an_unobserved_member_is_retained_and_does_not_become_a_flat_return(inputs):
    inputs['days'][0]['rows'][1]['is_trading']=False
    data=m.project(inputs)
    assert data['availability']=='insufficient_coverage' and data['return_pct'] is data['max_drawdown_pct'] is None
    assert len(data['points'])==3 and all(p['close'] is None for p in data['points'])
    assert data['points'][0]['member_count']==2 and data['points'][0]['observed_members']==1
    assert data['points'][0]['missing_symbols']==['000002.SZ'] and data['points'][0]['daily_return_pct']==10


def test_one_failed_late_day_cannot_leave_a_shortened_successful_path(inputs):
    inputs['days'][-1]['rows'][-1]['is_trading']=False
    data=m.project(inputs)
    assert data['availability']=='insufficient_coverage' and all(p['close'] is None for p in data['points'])
    assert data['points'][-1]['member_count']==1 and data['points'][-1]['observed_members']==0


def test_the_existing_95_percent_gate_is_inclusive_and_not_fit_to_returns(inputs):
    codes=[f'{n:06}' for n in range(1,21)];inputs['anchor']=[{'ts_code':code+'.SZ','name':'ST样本'+code} for code in codes];inputs['proofs']=[]
    inputs['endpoint_members']=[code+'.SZ' for code in codes]
    for day in inputs['days']:
        day['rows']=[row(code,'ST样本'+code,active=index>0) for index,code in enumerate(codes)];day['source_marked']=list(inputs['endpoint_members'])
    assert m.project(inputs)['availability']=='observed' and m.project(inputs)['minimum_coverage']==.95
    inputs['days'][-1]['rows'][1]['is_trading']=False
    assert m.project(inputs)['availability']=='insufficient_coverage'


def test_source_change_hides_old_reference_without_writing_or_collecting(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(m,'collect_inputs',lambda **_:deepcopy(inputs));m.materialize(output=tmp_path,now=NOW)
    path=tmp_path/'current.json';before=path.read_bytes();inputs['history_materialized_at']='2026-11-05T04:02:00+00:00'
    assert m.reference_status(tmp_path,now=NOW)['availability']=='source_changed' and path.read_bytes()==before


def test_injected_report_cannot_promote_a_reference_or_calibration_flag(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(m,'collect_inputs',lambda **_:deepcopy(inputs));m.materialize(output=tmp_path,now=NOW)
    path=tmp_path/'current.json';raw=json.loads(path.read_text());raw['report']={'return_pct':999,'portfolio_wealth':True,'effect_measured':True}
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});path.write_text(json.dumps(raw))
    data=m.reference_status(tmp_path,now=NOW)
    assert data['return_pct']==pytest.approx(-1) and data['effect_measured'] is data['portfolio_wealth'] is False


def test_mid_materialization_change_or_foreign_output_preserves_current(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(m,'collect_inputs',lambda **_:deepcopy(inputs));m.materialize(output=tmp_path,now=NOW);path=tmp_path/'current.json';before=path.read_bytes()
    changed=deepcopy(inputs);changed['history_materialized_at']='changed';sequence=iter([deepcopy(inputs),changed])
    monkeypatch.setattr(m,'collect_inputs',lambda **_:next(sequence))
    with pytest.raises(ValueError,match='source changed'):m.materialize(output=tmp_path,now=NOW)
    assert path.read_bytes()==before
    path.write_text('{"version":"foreign"}');before=path.read_bytes()
    with pytest.raises(ValueError,match='foreign'):m.materialize(output=tmp_path,now=NOW)
    assert path.read_bytes()==before


def test_processor_change_during_materialization_preserves_current(inputs,tmp_path,monkeypatch):
    monkeypatch.setattr(m,'collect_inputs',lambda **_:deepcopy(inputs));m.materialize(output=tmp_path,now=NOW)
    before=(tmp_path/'current.json').read_bytes();sequence=iter([m.PROCESSOR,'changed'])
    monkeypatch.setattr(m,'processor_digest',lambda:next(sequence))
    with pytest.raises(ValueError,match='processor/source changed'):m.materialize(output=tmp_path,now=NOW)
    assert (tmp_path/'current.json').read_bytes()==before


@pytest.mark.parametrize('availability',['observed','insufficient_coverage','source_changed'])
def test_reference_is_separate_from_the_complete_market_ST_gate(tmp_path,monkeypatch,availability):
    from market_risk import build_market_risk_status,market_update_status
    fake={'availability':availability,'start':'2026-09-04','through':'2026-11-04','member_day_observations':100,
          'source_fetched_at':NOW.isoformat(),'content_digest':'synthetic','combined_ST_ready':False,'effect_measured':False}
    monkeypatch.setattr('market_risk.szse_st_reference_status',lambda *args,**kwargs:deepcopy(fake))
    monkeypatch.setattr('market_risk._public_indices',lambda *args:({'availability':'observed','through':'2026-11-04','content_digest':'synthetic'},
        [{'code':'000985.CSI','through':'2026-11-04','historical_only':False,'observation_count':38}]))
    status=build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'missing.db',manifest_path=tmp_path/'missing.json',now=NOW)
    assert status['market_coverage']['st_style_at_target'] is False
    assert status['market_coverage']['st_reference_venues_at_target']==int(availability=='observed')
    assert status['market_coverage']['declared_indices']==3 and len(status['indices'])==1
    assert status['node_market_comparison']['status']=='not_evaluated' and status['parameters']['risk_weights'] is None
    update=next(r for r in market_update_status(snapshot_dir=tmp_path,now=NOW) if r['source_id']=='szse_st_price_reference')
    assert update['series_at_target']==int(availability=='observed') and update['declared_series']==2
    assert update['observed_through_min']=='2026-09-04' and update['observed_through_max']=='2026-11-04'
    assert update['observation_unit']=='成员日' and update['coverage_unit']=='交易所'


@pytest.mark.parametrize('kind',['warning_added','warning_removed','delisting_period','listing_end'])
def test_notice_proofs_bind_actual_effective_fields_instead_of_a_title(tmp_path,monkeypatch,kind):
    old,new=('样本','ST样本') if kind=='warning_added' else ('ST样本','样本')
    if kind=='delisting_period':new='样本退'
    if kind=='listing_end':new=None
    sentence=f'股票简称：由“{old}”变更为“{new}”。实施起始日：2026年9月8日'
    if kind=='delisting_period':sentence='公司股票于2026年9月8日复牌并进入退市整理期。证券简称：样本退'
    if kind=='listing_end':sentence='终止上市决定日期：2026年9月1日。摘牌日期：2026年9月8日'
    pages={'pages':[f'证券代码：000001证券简称：{old}样本股份有限公司'+sentence]}
    raw=b'%PDF-synthetic-source-proof';text=json.dumps(pages,ensure_ascii=False).encode()
    item={'symbol':'000001','company':'样本股份有限公司','old_name':old,'new_name':new,'kind':kind,'effective_on':'2026-09-08','page_count':1,'proof_page':1,
          'date_label':None if kind=='delisting_period' else '摘牌日期' if kind=='listing_end' else '实施起始日','observed_at':(NOW-timedelta(minutes=1)).isoformat(),
          'raw_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(text).hexdigest()}
    monkeypatch.setattr(m,'EVENTS',[item]);(tmp_path/(item['raw_sha256']+'.pdf')).write_bytes(raw);(tmp_path/(item['text_sha256']+'.json')).write_bytes(text)
    assert m.notice_proofs(tmp_path,NOW)[0]['effective_on']=='2026-09-08'


@pytest.mark.parametrize('bad',['bytes','text','code','company','date_role','direction','future','missing'])
def test_notice_metadata_and_raw_evidence_cannot_be_rebound(tmp_path,monkeypatch,bad):
    pages={'pages':['证券代码：000001证券简称：公司甲公司甲股份有限公司股票简称：由“公司甲”变更为“ST公司甲”。实施起始日：2026年9月8日']}
    raw=b'%PDF-synthetic-source-proof';text=json.dumps(pages,ensure_ascii=False).encode()
    case={'symbol':'000001','company':'公司甲股份有限公司','old_name':'公司甲','new_name':'ST公司甲','kind':'warning_added','effective_on':'2026-09-08',
          'page_count':1,'proof_page':1,'date_label':'实施起始日','observed_at':NOW.isoformat(),
          'raw_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(text).hexdigest()}
    (tmp_path/(case['raw_sha256']+'.pdf')).write_bytes(raw);(tmp_path/(case['text_sha256']+'.json')).write_bytes(text)
    if bad=='bytes':(tmp_path/(case['raw_sha256']+'.pdf')).write_bytes(raw+b'changed')
    elif bad=='text':(tmp_path/(case['text_sha256']+'.json')).write_bytes(text+b'changed')
    elif bad=='code':case['symbol']='000002'
    elif bad=='company':case['company']='另公司股份有限公司'
    elif bad=='date_role':case['date_label']='终止上市决定日期'
    elif bad=='direction':case['old_name'],case['new_name']=case['new_name'],case['old_name']
    elif bad=='future':case['observed_at']=(NOW+timedelta(days=1)).isoformat()
    else:(tmp_path/(case['raw_sha256']+'.pdf')).rename(tmp_path/'source.unavailable')
    monkeypatch.setattr(m,'EVENTS',[case])
    with pytest.raises((ValueError,OSError)):m.notice_proofs(tmp_path,NOW)
