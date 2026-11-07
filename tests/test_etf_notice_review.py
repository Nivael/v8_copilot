from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
from etf_notice_review import FUND_NAMES, notice_review_status, parse_reviewed_notice, repeated_allocations

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
CODE = '510330.SH'


def sample(category='portfolio_allocation'):
    name = FUND_NAMES[CODE]
    purpose = '本公司旗下基金参与了示例证券首次公开发行股票的申购。'
    row = name+'网下示例证券1,200123,456.78'
    pages = [purpose+'获配数量(股)获配金额(元)', row]
    case = {'code':CODE, 'category':category, 'purpose':{'page':1,'text':purpose}, 'allocations':[
        {'fund_name':name,'issuer':'示例证券','asset_unit':'stock_share','quantity_source':'1,200','amount_source':'123,456.78',
         'row_prefix':name+'网下示例证券','row_suffix':'','unit_evidence':{'page':1,'text':'获配数量(股)'},'row_evidence':{'page':2,'text':row}}]}
    return pages, case


def test_portfolio_stock_units_and_exact_amounts_cannot_become_fund_shares_or_cash_flows():
    pages, case = sample(); original = deepcopy(case)
    result = parse_reviewed_notice(pages, case)
    assert result['allocations'] == [{'issuer':'示例证券','asset_unit':'stock_share','quantity':'1200','amount_yuan':'123456.78','table_page':2}]
    assert result['fund_share_change_verified'] is result['full_document_semantics_checked'] is False
    assert result['evidence_pages'] == [1,2] and case == original


@pytest.mark.parametrize('change', ['unit','fund','feeder','quantity','amount','ambiguous','purpose','issuer','row_page','unit_page','category'])
def test_changed_clauses_wrong_fund_rows_units_and_values_require_another_review(change):
    pages, case = sample(); row = case['allocations'][0]
    if change == 'unit': row['asset_unit'] = 'fund_share'
    elif change == 'fund': case['code'] = '510310.SH'
    elif change == 'feeder': row['row_prefix'] += '联接基金'
    elif change == 'quantity': row['quantity_source'] = '1201'
    elif change == 'amount': row['amount_source'] = '123456.79'
    elif change == 'ambiguous': pages[1] += pages[1]
    elif change == 'purpose': pages[0] = pages[0].replace('参与了','拟参与')
    elif change == 'issuer': row['issuer'] = '另一家公司'
    elif change == 'row_page': row['row_evidence']['page'] = 1
    elif change == 'unit_page': row['unit_evidence']['page'] = 3
    else: case['category'] = 'net_redemption'
    with pytest.raises(ValueError): parse_reviewed_notice(pages, case)


def test_convertible_bond_pieces_remain_distinct_from_stock_shares():
    pages, case = sample(); case['allocations'][0]['asset_unit'] = 'bond_piece'
    case['allocations'][0]['unit_evidence']['text'] = '获配数量(张)'
    pages[0] = pages[0].replace('获配数量(股)','获配数量(张)')
    result = parse_reviewed_notice(pages, case)
    assert result['allocations'][0]['asset_unit'] == 'bond_piece'


def risk_sample():
    pages, case = sample('listing_valuation_risk')
    purpose = '示例证券将于2026年9月11日挂牌上市。'
    context = '表格中基金资产净值为2026年9月10日数据'
    risk = '上市首日IOPV只含发行价格,未包含新股的市场价格波动。'
    pages[0] = purpose+context+risk+'获配数量(股)'
    pages[1] += '0.00%网下'
    case.update(purpose={'page':1,'text':purpose},context={'page':1,'text':context},risk_evidence={'page':1,'text':risk},
                listing_on='2026年9月11日',nav_reference_on='2026年9月10日',reported_weight_text='0.00%')
    case['allocations'][0]['row_suffix'] = '0.00%网下'
    case['allocations'][0]['row_evidence']['text'] = pages[1]
    return pages, case


def test_listing_risk_keeps_rounded_weight_and_previous_nav_reference_date_separate():
    pages, case = risk_sample(); result = parse_reviewed_notice(pages, case)
    assert result['listing_on'] == '2026-09-11' and result['nav_reference_on'] == '2026-09-10'
    assert result['reported_weight_text'] == '0.00%' and result['allocations'][0]['quantity'] == '1200'
    case['reported_weight_text'] = '0.01%'
    with pytest.raises(ValueError): parse_reviewed_notice(pages, case)


def service_sample():
    purpose = '自2026年10月14日起增加申购赎回代办证券公司。'
    row = CODE[:6]+FUND_NAMES[CODE]+'示例证券股份有限公司'
    return [purpose+row], {'code':CODE,'category':'creation_redemption_agent','purpose':{'page':1,'text':purpose},'allocations':[],
                          'service':{'role':'申购赎回代办证券公司','provider':'示例证券股份有限公司','effective_on':'2026年10月14日','row_evidence':{'page':1,'text':row}}}


@pytest.mark.parametrize('field,value', [('provider','其他证券股份有限公司'),('effective_on','2026年10月15日'),('role','主流动性服务商')])
def test_service_providers_dates_and_roles_must_be_in_the_bound_clauses(field,value):
    pages, case = service_sample()
    assert parse_reviewed_notice(pages, case)['service']['effective_on'] == '2026-10-14'
    case['service'][field] = value
    with pytest.raises(ValueError): parse_reviewed_notice(pages, case)


def test_only_same_fund_security_quantity_and_amount_pairs_get_repeat_links_without_summing():
    pages, case = sample(); allocation = parse_reviewed_notice(pages, case)
    pages, case = risk_sample(); risk = parse_reviewed_notice(pages, case)
    a = {**allocation,'code':CODE,'document_id':'allocation'}
    b = {**risk,'code':CODE,'document_id':'risk'}
    before = deepcopy([a,b]); groups = repeated_allocations([a,b])
    assert len(groups) == 1 and groups[0]['document_ids'] == ['allocation','risk']
    assert groups[0]['quantity'] == '1200' and groups[0]['not_additional_subscription_flow'] is True
    assert [a,b] == before
    b['code'] = '510310.SH'
    assert repeated_allocations([a,b]) == []
    b['code'] = CODE; b['allocations'] = [{**b['allocations'][0],'amount_yuan':'123456.79'}]
    assert repeated_allocations([a,b]) == []
    b['allocations'] = deepcopy(a['allocations']); b['category'] = 'private_placement'
    assert repeated_allocations([a,b]) == []


def bound_source(tmp_path, monkeypatch):
    pages, case = sample()
    raw = json.dumps({'pages':pages}).encode(); key = hashlib.sha256(raw).hexdigest()
    (tmp_path/'document_text').mkdir(); (tmp_path/'document_text'/f'{key}.json').write_bytes(raw)
    case.update(document_id='reviewed',published_on='2026-09-05',text_sha256=key,raw_sha256='a'*64)
    document = {'code':CODE,'document_id':'reviewed','title':'披露标题','url':'https://www.sse.com.cn/n.pdf','published_on':'2026-09-05'}
    result = {'text_sha256':key,'format':'pdf','responses':[{'response_sha256':'a'*64,'url':document['url'],'observed_at':NOW.isoformat()}]}
    capture = {'documents':{'reviewed':result},'catalog_digest':'catalog','completed_at':NOW.isoformat()}
    capture['content_digest'] = digest(capture); (tmp_path/'document_capture.json').write_text(json.dumps(capture))
    announcements = {'availability':'observed','window_start':'2026-08-04','window_end':'2026-11-04','through':'2026-11-05',
                     'content_digest':'catalog','fulltext':{'availability':'observed','content_digest':capture['content_digest']},
                     'catalogs':[{'code':CODE,'required_documents':[document]}]}
    monkeypatch.setattr('etf_notice_review.NOTICE_CASES',[case])
    # The capture suite covers raw/archive tampering; these cases isolate the
    # closed review fingerprint and time/catalog joins.
    monkeypatch.setattr('etf_notice_review.valid_ready',lambda *a:True)
    return announcements, capture, case


def test_status_is_partial_and_counts_catalog_entries_separately_from_original_pdfs(tmp_path,monkeypatch):
    announcements, _, _ = bound_source(tmp_path,monkeypatch)
    status = notice_review_status(tmp_path,announcements,NOW)
    assert status['reviewed_notices'] == status['reviewed_funds'] == status['distinct_original_pdfs'] == 1
    assert status['availability'] == 'partial' and status['window_documents_outside_this_review'] == 0
    assert (status['catalog_window_start'],status['catalog_window_end']) == ('2026-08-04','2026-11-04')
    assert status['corporate_actions_checked'] is status['all_window_documents_reconciled'] is False


@pytest.mark.parametrize('change',['raw_fingerprint','text_fingerprint','code','date','future','before_publication','digest','outside_window'])
def test_changed_review_inputs_are_not_silently_reclassified_from_the_title(tmp_path,monkeypatch,change):
    announcements, capture, case = bound_source(tmp_path,monkeypatch)
    if change == 'raw_fingerprint': capture['documents']['reviewed']['responses'][0]['response_sha256'] = 'b'*64
    elif change == 'text_fingerprint': case['text_sha256'] = 'b'*64
    elif change == 'code': announcements['catalogs'][0]['required_documents'][0]['code'] = '510310.SH'
    elif change == 'date': case['published_on'] = '2026-09-06'
    elif change == 'future': capture['documents']['reviewed']['responses'][0]['observed_at'] = '2026-11-06T00:00:00+00:00'
    elif change == 'before_publication': capture['documents']['reviewed']['responses'][0]['observed_at'] = '2026-09-04T00:00:00+00:00'
    elif change == 'outside_window': announcements['window_start'] = '2026-10-01'
    capture.pop('content_digest'); capture['content_digest'] = digest(capture)
    announcements['fulltext']['content_digest'] = 'wrong' if change == 'digest' else capture['content_digest']
    (tmp_path/'document_capture.json').write_text(json.dumps(capture))
    assert notice_review_status(tmp_path,announcements,NOW)['reviewed_notices'] == 0


def test_unloaded_source_and_missing_capture_remain_unavailable(tmp_path,monkeypatch):
    assert notice_review_status(tmp_path,{},NOW)['availability'] == 'missing'
    monkeypatch.setattr('etf_notice_review.PARSER_DIGEST','unloaded')
    assert notice_review_status(tmp_path,{},NOW)['availability'] == 'reload_required'


def test_new_notice_facts_cannot_advance_market_dates_or_release_cash_flow_or_risk_estimates(tmp_path,monkeypatch):
    import market_risk
    folder = tmp_path/'etf_announcements'; folder.mkdir()
    announcements, _, _ = bound_source(folder,monkeypatch)
    monkeypatch.setattr(market_risk,'announcement_status',lambda *a:announcements)
    before = {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    status = market_risk.build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'none',manifest_path=tmp_path/'none',now=NOW)
    assert status['etf_notice_review']['reviewed_notices'] == 1
    assert status['requested_through'] is None and status['current_risk_assessment'] == 'not_calibrated'
    assert all(row['estimated_net_subscription_yuan'] is None for row in status['etf_aggregate'].values())
    assert before == {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
