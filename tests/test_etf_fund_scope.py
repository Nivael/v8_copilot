from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
import etf_fund_scope as m

NOW=datetime(2026,11,6,tzinfo=timezone.utc)
# Synthetic role-bearing passages: each reviewed field is independently exercised.
TEXTS={
 'version_dates':'财务数据截止日为2026年6月30日,净值表现截止日为2026年6月30日,主要人员情况截止日为2026年7月30日,其他所载内容截止日为2026年6月16日。财务数据未经审计',
 'registrars':'场内上市交易以及申购、赎回等相关业务的登记结算由中国结算负责办理;场外申购、赎回等相关业务的登记结算由易方达基金管理有限公司负责办理',
 'listed_identity':'交易代码:510310)',
 'listed_transfer':'申请办理跨系统转托管将基金份额转为场内份额后,方可上市交易',
 'iopv_rounding':'参考净值的计算以四舍五入的方法保留小数点后4位',
 'share_classes':'分为场内份额与场外份额两种',
 'order_and_consideration':'场内份额采用份额申购和份额赎回;场外份额采用金额申购、份额赎回;场内份额的申购对价、赎回对价包括组合证券、现金替代、现金差额及其他对价;场外份额的申购对价、赎回对价为现金',
 'off_subscription_rounding':'有效份额单位为份,份额计算结果按四舍五入方法保留到整数位;申购费用以人民币元为单位,四舍五入保留至小数点后两位',
 'off_redemption_rounding':'赎回金额、赎回费用的单位为人民币元,四舍五入保留到小数点两位',
 'registration_and_transfer':'认购、二级市场买入或场内申购的基金份额属场内份额,由中国结算负责办理登记结算;通过场外申购的基金份额属场外份额,由易方达基金管理有限公司负责办理登记结算;条件许可情况下,在基金管理人制定并发布有关规则后,本基金场外份额可跨系统转托管为场内份额;但除非基金管理人另行公告,场内份额不可跨系统转托管为场外份额',
 'nav_rounding':'基金份额净值是按照每日资产和份额计算,精确到0.0001元,小数点后第五位四舍五入',
 'distribution_mode':'场内及场外份额的收益分配方式均采用现金分红',
 'distribution_rounding':'每基金份额的应分配收益为金额除以对应份额,保留小数点后3位,第4位舍去',
}


def synthetic():
    profile=deepcopy(m.PROFILE);pages=['']*profile['document']['page_count'];pages[0]=profile['fund_name']+'更新的招募说明书基金管理人:'+profile['issuer']
    for proof in profile['proofs']:
        role=proof['role'];proof['start']='开始'+role;proof['end']='终止'+role
        block=proof['start']+TEXTS[role]+proof['end'];proof['sha256']=hashlib.sha256(block.encode()).hexdigest();pages[proof['page']-1]+=block+'。'
    return profile,pages


def test_registers_routes_version_exceptions_and_six_rounding_objects_remain_distinct():
    profile,pages=synthetic();data=m.parse_rules(pages,profile)
    assert data['cutoffs']=={'financial':'2026-06-30','NAV_performance':'2026-06-30','personnel':'2026-07-30','general_content':'2026-06-16'}
    assert data['registrars']['exchange']=='中国证券登记结算有限责任公司' and data['registrars']['off_exchange']=='易方达基金管理有限公司'
    transfer=data['transfer'];assert transfer['conditional'] is transfer['requires_published_rules'] is transfer['reverse_requires_separate_announcement'] is True
    assert transfer['actual_window_transfers'] is None and transfer['daily_adjustment_applied'] is False
    assert [r['creation_application'] for r in data['routes']]==['shares','amount'] and data['routes'][1]['consideration']==['cash']
    assert [(r['target'],r['fractional_digits'],r['method']) for r in data['rounding_rules']]==[
        ('iopv',4,'half_up'),('off_exchange_subscribed_shares',0,'half_up'),('off_exchange_subscription_fee',2,'half_up'),
        ('off_exchange_redemption_payment_and_fee',2,'half_up'),('unit_NAV',4,'half_up'),('distribution_per_share',3,'truncate')]
    assert all(r['applies_to_exchange_daily_share_field'] is False for r in data['rounding_rules'])
    assert data['daily_exchange_share_rounding_rule'] is None and data['current_business_availability_verified'] is False


@pytest.mark.parametrize('bad',['fund','issuer','code','missing_role','duplicate_role','wrong_page','changed_passage','reclassify_iopv','swap_registers',
    'unconditional_transfer','reverse_transfer','wrong_cash_route','NAV_precision','money_precision','share_precision','distribution_method','cutoff_date_role','future_cutoff'])
def test_identity_date_actor_unit_and_rule_roles_cannot_be_rebound_even_with_new_passage_hash(bad):
    profile,pages=synthetic()
    if bad=='fund':pages[0]=pages[0].replace(profile['fund_name'],'另一只基金')
    elif bad=='issuer':pages[0]=pages[0].replace(profile['issuer'],'另一家基金管理人')
    elif bad=='missing_role':profile['proofs'].pop()
    elif bad=='duplicate_role':profile['proofs'].append(deepcopy(profile['proofs'][0]))
    elif bad=='wrong_page':profile['proofs'][0]['page']=2
    elif bad=='changed_passage':pages[3]+='x';proof=profile['proofs'][0];pages[3]=pages[3].replace('未经审计','已审计')
    else:
        roles={'code':'listed_identity','reclassify_iopv':'iopv_rounding','swap_registers':'registration_and_transfer','unconditional_transfer':'registration_and_transfer',
          'reverse_transfer':'registration_and_transfer','wrong_cash_route':'order_and_consideration','NAV_precision':'nav_rounding','money_precision':'off_redemption_rounding',
          'share_precision':'off_subscription_rounding','distribution_method':'distribution_rounding','cutoff_date_role':'version_dates','future_cutoff':'version_dates'}
        proof=next(p for p in profile['proofs'] if p['role']==roles[bad]);text=pages[proof['page']-1]
        changes={'code':('510310','510300'),'reclassify_iopv':('参考净值','基金份额净值'),'swap_registers':('由中国结算负责办理登记结算','由易方达基金管理有限公司负责办理登记结算'),
          'unconditional_transfer':('条件许可情况下,在基金管理人制定并发布有关规则后,',''), 'reverse_transfer':('场内份额不可跨系统','场内份额可跨系统'),
          'wrong_cash_route':('场外份额的申购对价、赎回对价为现金','场外份额的申购对价、赎回对价为证券'), 'NAV_precision':('0.0001元','0.01元'),
          'money_precision':('小数点两位','小数点四位'),'share_precision':('整数位','小数点两位'),'distribution_method':('第4位舍去','第4位四舍五入'),
          'cutoff_date_role':('主要人员情况截止日','总内容截止日'),'future_cutoff':('2026年7月30日','2026年8月1日')}
        old,new=changes[bad];text=text.replace(old,new);pages[proof['page']-1]=text
        a=text.index(proof['start']);b=text.index(proof['end'],a)+len(proof['end']);proof['sha256']=hashlib.sha256(text[a:b].encode()).hexdigest()
    with pytest.raises(ValueError):m.parse_rules(pages,profile)


@pytest.fixture
def capture(tmp_path,monkeypatch):
    profile,pages=synthetic();ref=profile['document'];pdf=b'%PDF-synthetic-scoped-rule-source';text=json.dumps({'pages':pages},ensure_ascii=False).encode()
    ref.update(raw_sha256=hashlib.sha256(pdf).hexdigest(),text_sha256=hashlib.sha256(text).hexdigest(),bytes=len(pdf))
    folder=tmp_path/'etf_fund_scope';folder.mkdir();(folder/(ref['raw_sha256']+'.pdf')).write_bytes(pdf);(folder/(ref['text_sha256']+'.json')).write_bytes(text);(folder/'source.json').write_text(json.dumps(ref))
    meta={'availability':'observed','content_digest':ref['catalog_digest']};catalogs={ref['code']:{'records':[{k:ref[k] for k in ('document_id','code','published_on','title','url')}]}}
    monkeypatch.setattr(m,'PROFILE',profile);monkeypatch.setattr(m,'load_announcement_catalog',lambda *a,**k:(meta,catalogs))
    return folder,tmp_path,meta,catalogs


@pytest.mark.parametrize('bad',['pdf','text','source_metadata','URL','catalog_hash','catalog_item','catalog_state','observation','naive_observation'])
def test_raw_and_catalog_bindings_are_required(capture,bad):
    folder,root,meta,catalogs=capture;ref=m.PROFILE['document']
    if bad=='pdf':(folder/(ref['raw_sha256']+'.pdf')).write_bytes(b'changed')
    elif bad=='text':(folder/(ref['text_sha256']+'.json')).write_text('{}')
    elif bad=='source_metadata':d=json.loads((folder/'source.json').read_text());d['published_on']='2026-08-01';(folder/'source.json').write_text(json.dumps(d))
    elif bad=='URL':ref['response_url']='https://other.example/doc.pdf';(folder/'source.json').write_text(json.dumps(ref))
    elif bad=='catalog_hash':meta['content_digest']='changed'
    elif bad=='catalog_item':catalogs[ref['code']]['records'][0]['document_id']='other'
    elif bad=='catalog_state':meta['availability']='invalid'
    else:ref['observed_at']='2026-11-07T00:00:00+00:00' if bad=='observation' else '2026-11-05T10:00:00';(folder/'source.json').write_text(json.dumps(ref))
    with pytest.raises((ValueError,KeyError)):m.collect_inputs(folder,root=root,now=NOW)


def test_GET_recomputes_rules_and_does_not_trust_injected_daily_certification(capture,monkeypatch):
    folder,root,*_=capture;inputs=m.collect_inputs(folder,root=root,now=NOW);monkeypatch.setattr(m,'collect_inputs',lambda *a,**k:deepcopy(inputs))
    m.materialize(folder,root=root,now=NOW);path=folder/'current.json';raw=json.loads(path.read_text())
    raw['report']={'whole_fund_daily_scope_verified':True,'share_precision_verified':True,'estimated_net_subscription_yuan':999,'reviewed_documents':8}
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});path.write_text(json.dumps(raw));before=path.read_bytes();data=m.scope_status(folder,root=root,now=NOW)
    assert data['reviewed_documents']==1 and data['reviewed_passages']==13 and data['estimated_net_subscription_yuan'] is None
    assert all(data[k] is False for k in ('whole_fund_daily_scope_verified','share_precision_verified','final_revision_verified','corporate_actions_checked','full_document_semantics_checked','all_window_share_events_verified','historical_PIT','effect_measured'))
    assert path.read_bytes()==before
    inputs['document']['title']='changed';assert m.scope_status(folder,root=root,now=NOW)['availability']=='invalid' and path.read_bytes()==before


def test_changed_inputs_or_code_and_foreign_output_preserve_current(capture,monkeypatch):
    folder,root,*_=capture;inputs=m.collect_inputs(folder,root=root,now=NOW);monkeypatch.setattr(m,'collect_inputs',lambda *a,**k:deepcopy(inputs));m.materialize(folder,root=root,now=NOW);path=folder/'current.json';before=path.read_bytes()
    changed=deepcopy(inputs);changed['facts']['cutoffs']['financial']='2026-06-16';seq=iter([inputs,changed]);monkeypatch.setattr(m,'collect_inputs',lambda *a,**k:next(seq))
    with pytest.raises(ValueError,match='sources or processor'):m.materialize(folder,root=root,now=NOW)
    assert path.read_bytes()==before

    def read(*a,**k):
        if not k.get('full'):monkeypatch.setattr(m,'processor_digest',lambda:'changed')
        return deepcopy(inputs)
    monkeypatch.setattr(m,'collect_inputs',read)
    with pytest.raises(ValueError,match='sources or processor'):m.materialize(folder,root=root,now=NOW)
    assert path.read_bytes()==before and m.scope_status(folder,root=root,now=NOW)['availability']=='reload_required'
    monkeypatch.setattr(m,'processor_digest',lambda:m.PROCESSOR);path.write_text('{"version":"foreign"}');before=path.read_bytes()
    with pytest.raises(ValueError,match='foreign'):m.materialize(folder,root=root,now=NOW)
    assert path.read_bytes()==before

def test_one_prospectus_review_is_not_ETF_universe_or_daily_flow_certification(tmp_path,monkeypatch):
    import market_risk
    fake={'availability':'scoped_rules_reviewed','document':{'published_on':'2026-07-31','observed_at':'2026-11-05T10:00:00+00:00'},'reviewed_documents':1,'reviewed_passages':13}
    monkeypatch.setattr(market_risk,'fund_scope_status',lambda *a,**k:deepcopy(fake))
    status=market_risk.build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'missing.db',manifest_path=tmp_path/'missing.json',now=NOW)
    assert status['parameter_version']=='market_risk_parameters_v6' and status['parameters']['risk_weights'] is None
    assert status['etf_aggregate']['5']['estimated_net_subscription_yuan'] is None and status['market_coverage']['st_style_at_target'] is False
    row=next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path,now=NOW) if r['source_id']=='etf_fund_scope_rules')
    assert row['observation_count']==1 and row['observed_source_groups']==row['declared_series']==13 and row['series_at_target'] is None
    assert row['date_basis']=='prospectus_publication' and row['observed_through_min']=='2026-07-31' and row['requested_through'] is None
