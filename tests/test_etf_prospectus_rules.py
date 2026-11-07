from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json

import pytest

from canonical_json import digest
from etf_prospectus_rules import CASES,FUND_NAMES,all_proofs,parse_prospectus_rules,prospectus_rule_status

NOW=datetime(2026,11,5,tzinfo=timezone.utc)


def pages_for(case):
    """Synthetic source pages isolate negative boundaries without shipping full PDFs."""
    pages=['']*max(item['page'] for item in all_proofs(case))
    pages[0]=FUND_NAMES[case['code']]+'更新招募说明书'
    for item in all_proofs(case):pages[item['page']-1]+=item['text']+'。'
    return pages


def test_publication_cutoffs_and_financial_dates_do_not_turn_old_rules_into_current_events():
    case=deepcopy(CASES[0]);result=parse_prospectus_rules(pages_for(case),case)
    assert result['content_asof']=='2026-07-31' and result['financial_data_asof']=='2026-06-30'
    assert result['cash_is_only_consideration'] is False
    assert result['distribution_mode_as_stated']=='cash' and result['max_annual_distributions_as_stated']==4
    assert result['actual_distributions_in_market_window'] is result['current_cash_flow_yuan'] is None
    assert result['corporate_actions_checked'] is result['full_document_semantics_checked'] is result['market_window_correction_applied'] is False
    assert all(row['effective_at_market_target']=='not_verified' for row in result['minimum_units'])


def test_business_routes_keep_distinct_quantities_without_a_fund_total_multiplier():
    case=deepcopy(CASES[1])
    case['minimum_units'][1]['clause']['text']=case['minimum_units'][1]['clause']['text'].replace('100万份','80万份')
    result=parse_prospectus_rules(pages_for(case),case)
    assert [row['stated_unit_shares'] for row in result['minimum_units']]==['1000000','800000','1000000']
    assert all(row['quantity_scope']=='fund_shares_per_business_unit' for row in result['minimum_units'])
    assert result['max_annual_distributions_as_stated']==12 and result['cutoff_exception']=='特别事项注明除外'
    assert result['illustration'] is None


def test_hypothetical_example_and_later_historical_restatement_never_share_a_current_factor():
    case=deepcopy(CASES[0]);result=parse_prospectus_rules(pages_for(case),case)
    assert result['illustration']['classification']=='hypothetical_illustration'
    assert result['illustration']['stated_ratio']=='0.26671819'
    assert result['illustration']['after_shares']=='1334' and result['illustration']['not_a_verified_event'] is True
    history=result['historical_restatement']
    assert (history['event_on'],history['registered_on'],history['stated_ratio'])==('2012-05-11','2012-05-14','0.37094933')
    assert history['not_historical_point_in_time_evidence'] is True
    # A different, internally valid hypothetical example still cannot alter
    # the historical factor, create an effective current factor or apply it.
    case['illustration']['calculation']['text']=case['illustration']['calculation']['text'].replace('0.26671819=1,334','0.30000000=1,500')
    changed=parse_prospectus_rules(pages_for(case),case)
    assert changed['historical_restatement']==history and 'effective_ratio' not in changed
    assert changed['market_window_correction_applied'] is False


@pytest.mark.parametrize('change',['identity','missing_clause','duplicate_clause','changed_number','zero_unit','fractional_unit','missing_route','duplicate_route','heading_after_clause','future_content','financial_date','audit','consideration','distribution_mode','history_date','history_rounding','example_premise','example_math','example_quantity'])
def test_changed_clauses_ambiguous_scope_or_inconsistent_rules_fail_closed(change):
    case=deepcopy(CASES[0])
    if change=='zero_unit':case['minimum_units'][0]['clause']['text']=case['minimum_units'][0]['clause']['text'].replace('90万份','0万份')
    elif change=='fractional_unit':case['minimum_units'][0]['clause']['text']=case['minimum_units'][0]['clause']['text'].replace('90万份','90.5万份')
    elif change=='missing_route':case['minimum_units'].pop()
    elif change=='duplicate_route':case['minimum_units'][1]['route']=case['minimum_units'][0]['route']
    elif change=='heading_after_clause':case['minimum_units'][0]['heading']['page']=44
    elif change=='future_content':case['cutoffs']['text']=case['cutoffs']['text'].replace('2026年07月31日','2026年08月14日')
    elif change=='financial_date':case['cutoffs']['text']=case['cutoffs']['text'].replace('2026年06月30日','2026年08月01日')
    elif change=='audit':case['cutoffs']['text']=case['cutoffs']['text'].replace('未经审计','已经审计')
    elif change=='consideration':case['consideration']['text']='申购和赎回只使用现金。'
    elif change=='distribution_mode':case['cash_distribution']['text']='收益分配采用红利再投资;'
    elif change=='history_date':case['history']['date']['text']=case['history']['date']['text'].replace('2012年','2027年')
    elif change=='history_rounding':case['history']['rounding']['text']='折算份额处理规则未列明。'
    elif change=='example_premise':case['illustration']['premise']['text']=case['illustration']['premise']['text'].replace('举例假设','实际发生')
    elif change=='example_math':case['illustration']['calculation']['text']=case['illustration']['calculation']['text'].replace('1,334','1,333')
    elif change=='example_quantity':case['illustration']['calculation']['text']=case['illustration']['calculation']['text'].replace('5,000','6,000').replace('1,334','1,600')
    pages=pages_for(case)
    if change=='identity':pages[0]='另一只基金更新招募说明书'
    elif change=='missing_clause':pages[34]=pages[34].replace(case['consideration']['text'],'')
    elif change=='duplicate_clause':pages[34]+=case['minimum_units'][0]['clause']['text']
    elif change=='changed_number':pages[34]=pages[34].replace('90万份','91万份')
    with pytest.raises(ValueError):parse_prospectus_rules(pages,case)


def bound_version(tmp_path,monkeypatch):
    case=deepcopy(CASES[0]);raw=json.dumps({'pages':pages_for(case)}).encode();sha=hashlib.sha256(raw).hexdigest()
    (tmp_path/'document_text').mkdir();(tmp_path/'document_text'/f'{sha}.json').write_bytes(raw)
    case['text_sha256']=sha;case['raw_sha256']='a'*64
    document={key:case[key] for key in ('code','document_id','published_on')}
    document.update(title='更新招募说明书',url='https://www.sse.com.cn/prospectus.pdf')
    result={'format':'pdf','text_sha256':sha,'responses':[{'url':document['url'],'response_sha256':'a'*64,'observed_at':NOW.isoformat()}]}
    capture={'documents':{case['document_id']:result},'catalog_digest':'catalog','completed_at':NOW.isoformat()}
    capture['content_digest']=digest(capture);(tmp_path/'document_capture.json').write_text(json.dumps(capture))
    announcements={'availability':'observed','content_digest':'catalog','through':'2026-11-05',
                   'fulltext':{'availability':'observed','content_digest':capture['content_digest']},
                   'catalogs':[{'code':case['code'],'required_documents':[document]}]}
    monkeypatch.setattr('etf_prospectus_rules.CASES',[case])
    # Raw archive integrity has dedicated capture tests. This fixture keeps
    # text-byte checks and isolates version fingerprints/availability joins.
    monkeypatch.setattr('etf_quarterly.valid_ready',lambda *a:True)
    return announcements,capture,case


def test_status_keeps_publication_observation_and_content_dates_separate(tmp_path,monkeypatch):
    announcements,_,_=bound_version(tmp_path,monkeypatch)
    status=prospectus_rule_status(tmp_path,announcements,NOW)
    assert status['availability']=='partial' and status['reviewed_versions']==status['selected_prospectus_versions']==1
    version=status['versions'][0]
    assert version['publication_date']=='2026-08-13' and version['content_asof']=='2026-07-31'
    assert version['document_observed_at']==NOW.isoformat()
    assert status['corporate_actions_checked'] is status['all_window_documents_reconciled'] is False


@pytest.mark.parametrize('change',['raw','text','catalog','pub','observation_future','observation_before_publication','missing','bytes'])
def test_changed_or_unavailable_reviewed_version_never_falls_back_to_a_title(tmp_path,monkeypatch,change):
    announcements,capture,case=bound_version(tmp_path,monkeypatch);record=capture['documents'][case['document_id']]
    if change=='raw':record['responses'][0]['response_sha256']='b'*64
    elif change=='text':case['text_sha256']='b'*64
    elif change=='catalog':capture['catalog_digest']='other'
    elif change=='pub':announcements['catalogs'][0]['required_documents'][0]['published_on']='2026-08-14'
    elif change=='observation_future':record['responses'][0]['observed_at']='2026-11-06T00:00:00+00:00'
    elif change=='observation_before_publication':record['responses'][0]['observed_at']='2026-08-12T00:00:00+00:00'
    elif change=='missing':announcements['catalogs'][0]['required_documents']=[]
    elif change=='bytes':(tmp_path/'document_text'/f"{case['text_sha256']}.json").write_text('changed')
    capture.pop('content_digest');capture['content_digest']=digest(capture)
    announcements['fulltext']['content_digest']=capture['content_digest']
    (tmp_path/'document_capture.json').write_text(json.dumps(capture))
    assert prospectus_rule_status(tmp_path,announcements,NOW)['reviewed_versions']==0


def test_missing_inventory_and_unloaded_rule_reader_do_not_publish_a_version(tmp_path,monkeypatch):
    assert prospectus_rule_status(tmp_path,{},NOW)['availability']=='missing'
    monkeypatch.setattr('etf_prospectus_rules.PARSER_DIGEST','changed')
    assert prospectus_rule_status(tmp_path,{},NOW)['availability']=='reload_required'


def test_rule_reviews_cannot_advance_market_dates_or_release_cash_flow_estimates(tmp_path,monkeypatch):
    import market_risk
    folder=tmp_path/'etf_announcements';folder.mkdir()
    announcements,_,_=bound_version(folder,monkeypatch)
    monkeypatch.setattr(market_risk,'announcement_status',lambda *a:announcements)
    before={str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    status=market_risk.build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'none',manifest_path=tmp_path/'none',now=NOW)
    assert status['etf_prospectus_rules']['reviewed_versions']==1 and status['requested_through'] is None
    assert all(row['estimated_net_subscription_yuan'] is None for row in status['etf_aggregate'].values())
    assert status['current_risk_assessment']=='not_calibrated' and status['node_market_comparison']['status']=='not_evaluated'
    assert before=={str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
