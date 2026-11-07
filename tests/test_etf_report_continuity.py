from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
from etf_quarterly import parse_midyear_report, parse_report, quarterly_status
from etf_report_continuity import compare_adjacent_reports, report_continuity_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
CODE = "510310.SH"


def midyear_pages():
    return ["2026年中期报告 本报告期自2026年1月1日起至6月30日止。本报告中财务资料未经审计。"
            "基金名称示例指数证券投资基金 基金简称示例 基金主代码510310 报告期末基金份额总额1,000.00份",
            "§9 开放式基金份额变动..........60 §10 重大事件揭示........61",
            "§9 开放式基金份额变动 单位：份 基金合同生效日（2013年3月6日）基金份额总额1,104,307,415.00"
            "本报告期期初基金份额总额2,000.00 本报告期基金总申购份额100.00 减：本报告期基金总赎回份额1,100.00"
            "本报告期基金拆分变动份额- 本报告期期末基金份额总额1,000.00"
            "注：期初基金总份额包含场外份额20份；期末基金总份额包含场外份额10份；"
            "总申购份额包含场外总申购份额0份；总赎回份额包含场外总赎回份额10份。§10 重大事件揭示"]


def quarterly_pages():
    return ["2026年第3季度报告 本报告期自2026年7月1日起至9月30日止。基金主代码510310报告期末基金份额总额1,030.00份",
            "§6开放式基金份额变动单位：份报告期期初基金份额总额1,000.00报告期期间基金总申购份额50.00"
            "减：报告期期间基金总赎回份额20.00报告期期间基金拆分变动份额-报告期期末基金份额总额1,030.00"
            "注：期初基金总份额包含场外份额10份；期末基金总份额包含场外份额10份。§7基金管理人"]


def test_midyear_uses_actual_halfyear_period_and_opening_instead_of_inception_total():
    report = parse_midyear_report(midyear_pages(), CODE, 2026)
    assert (report['period_start'], report['period_end']) == ('2026-01-01', '2026-06-30')
    assert report['opening_shares'] == '2000.00' and report['net_subscription_shares'] == '-1000.00'
    assert report['closing_shares'] == '1000.00' and report['table_page'] == 3
    assert report['reported_split_shares'] is None and report['split_entry'] == '-'
    assert report['off_exchange_closing_shares'] == '10'
    assert report['audit_status'] == 'report_states_unaudited'


def test_cross_page_table_accepts_only_the_identified_fund_and_exact_printed_header():
    pages = midyear_pages()
    heading, body = pages.pop().split(' 单位：份', 1)
    pages += [heading, '示例指数证券投资基金2026年中期报告第3页共3页 单位：份' + body]
    assert parse_midyear_report(pages, CODE, 2026)['table_page'] == 4
    for before, after in [('示例指数证券投资基金2026年', '其他基金2026年'), ('第3页共3页', '第2页共3页'),
                          ('第3页共3页', '第3页共4页')]:
        bad = pages.copy(); bad[-1] = bad[-1].replace(before, after)
        with pytest.raises(ValueError): parse_midyear_report(bad, CODE, 2026)


@pytest.mark.parametrize('change', ['year', 'dates', 'identity', 'units', 'summary', 'balance', 'duplicate', 'inception', 'off_scope'])
def test_midyear_rejects_ambiguous_or_inconsistent_report(change):
    pages = midyear_pages()
    if change == 'year': pages[0] = pages[0].replace('2026年中期报告', '2025年中期报告')
    elif change == 'dates': pages[0] = pages[0].replace('1月1日', '7月1日')
    elif change == 'identity': pages[0] = pages[0].replace('代码510310', '代码510300')
    elif change == 'units': pages[-1] = pages[-1].replace('单位：份', '单位：万份')
    elif change == 'summary': pages[0] = pages[0].replace('1,000.00', '1,001.00')
    elif change == 'balance': pages[-1] = pages[-1].replace('总申购份额100.00', '总申购份额101.00')
    elif change == 'duplicate': pages.append(pages[-1])
    elif change == 'inception': pages[-1] = pages[-1].replace('1,104,307,415.00', '1,104,30,7415.00')
    else: pages[-1] = pages[-1].replace('期末基金总份额包含场外份额10份', '期末场外未列明')
    with pytest.raises(ValueError): parse_midyear_report(pages, CODE, 2026)


def observed_pair():
    return ({**parse_midyear_report(midyear_pages(), CODE, 2026), 'availability':'observed'},
            {**parse_report(quarterly_pages(), CODE, 2026, 3), 'availability':'observed'})


def test_total_continuity_and_separately_disclosed_off_exchange_scope_are_exact():
    previous, following = observed_pair()
    result = compare_adjacent_reports(previous, following)
    assert result['total_relation'] == result['off_exchange_relation'] == 'equal'
    assert result['total_difference_shares'] == '0.00'
    following['opening_shares'] = '999.99'; following['off_exchange_opening_shares'] = '11'
    result = compare_adjacent_reports(previous, following)
    assert result['total_difference_shares'] == '-0.01' and result['total_relation'] == 'different'
    assert result['off_exchange_difference_shares'] == '1' and result['off_exchange_relation'] == 'different'
    previous['off_exchange_closing_shares'] = None
    assert compare_adjacent_reports(previous, following)['off_exchange_difference_shares'] is None


@pytest.mark.parametrize('field,value', [('code','510300.SH'), ('period_start','2026-10-01'),
                                        ('share_scope','exchange_only'), ('share_unit','ten_thousand_shares')])
def test_incompatible_funds_periods_units_or_scope_are_never_matched(field, value):
    previous, following = observed_pair(); following[field] = value
    assert compare_adjacent_reports(previous, following)['availability'] == 'incompatible'
    following['availability'] = 'invalid'
    assert compare_adjacent_reports(previous, following)['availability'] == 'missing'


def bound_reports(tmp_path, monkeypatch):
    (tmp_path/'document_text').mkdir()
    documents, results = [], {}
    for key, title, published, pages in [('mid','2026年中期报告','2026-08-31',midyear_pages()),
                                          ('q3','2026年第3季度报告','2026-10-27',quarterly_pages())]:
        raw = json.dumps({'pages':pages}).encode(); sha = hashlib.sha256(raw).hexdigest()
        (tmp_path/'document_text'/f'{sha}.json').write_bytes(raw)
        documents.append({'document_id':key,'code':CODE,'title':title,'published_on':published,'url':f'https://www.sse.com.cn/{key}.pdf'})
        results[key] = {'text_sha256':sha,'format':'pdf','responses':[{'url':documents[-1]['url'],'observed_at':NOW.isoformat()}]}
    capture = {'documents':results,'catalog_digest':'catalog','completed_at':NOW.isoformat()}
    capture['content_digest'] = digest(capture)
    (tmp_path/'document_capture.json').write_text(json.dumps(capture))
    announcements = {'availability':'observed','through':'2026-11-05','content_digest':'catalog',
                     'fulltext':{'availability':'observed','content_digest':capture['content_digest']},
                     'catalogs':[{'code':CODE,'required_documents':documents}]}
    # Raw and extracted-byte binding has its own capture suite. These cases
    # isolate period/source joins while still checking extracted-text hashes.
    monkeypatch.setattr('etf_quarterly.valid_ready', lambda *a: True)
    quarterly = quarterly_status(tmp_path, announcements, [], '2026-11-04', NOW)
    return announcements, quarterly, capture


def test_reader_binds_both_periods_to_the_same_capture_and_preserves_missing_basket_members(tmp_path, monkeypatch):
    announcements, quarterly, _ = bound_reports(tmp_path, monkeypatch)
    before = deepcopy((announcements, quarterly))
    status = report_continuity_status(tmp_path, announcements, quarterly, NOW)
    assert status['availability'] == 'partial' and status['declared_etfs'] == 8
    assert status['observed_midyear_reports'] == status['compared_etfs'] == status['matched_etfs'] == 1
    assert status['mismatched_etfs'] == 0 and status['corporate_actions_checked'] is False
    assert status['reports'][1]['midyear_report']['publication_date'] == '2026-08-31'
    assert status['reports'][0]['comparison']['availability'] == 'missing'
    assert (announcements, quarterly) == before
    quarterly['capture_digest'] = 'different'
    assert report_continuity_status(tmp_path, announcements, quarterly, NOW)['availability'] == 'invalid'


@pytest.mark.parametrize('change', ['text', 'duplicate', 'observed_before_publication', 'bad_capture', 'missing_following'])
def test_reader_never_compares_unverified_or_ambiguous_inputs(tmp_path, monkeypatch, change):
    announcements, quarterly, capture = bound_reports(tmp_path, monkeypatch)
    if change == 'text': (tmp_path/'document_text'/f"{capture['documents']['mid']['text_sha256']}.json").write_text('tampered')
    elif change == 'duplicate': announcements['catalogs'][0]['required_documents'].append(deepcopy(announcements['catalogs'][0]['required_documents'][0]))
    elif change == 'observed_before_publication':
        capture['documents']['mid']['responses'][0]['observed_at'] = '2026-08-30T00:00:00+00:00'
        capture.pop('content_digest'); capture['content_digest'] = digest(capture)
        (tmp_path/'document_capture.json').write_text(json.dumps(capture))
        announcements['fulltext']['content_digest'] = quarterly['capture_digest'] = capture['content_digest']
    elif change == 'bad_capture': (tmp_path/'document_capture.json').write_text('{}')
    else: quarterly['reports'][0]['availability'] = 'invalid'
    status = report_continuity_status(tmp_path, announcements, quarterly, NOW)
    assert status['compared_etfs'] == status['matched_etfs'] == 0


def test_nonadjacent_quarter_and_unloaded_code_do_not_publish_a_comparison(tmp_path, monkeypatch):
    announcements, quarterly, _ = bound_reports(tmp_path, monkeypatch)
    assert report_continuity_status(tmp_path, announcements, {'availability':'missing'}, NOW)['availability'] == 'missing'
    quarterly['period_start'] = '2026-10-01'
    assert report_continuity_status(tmp_path, announcements, quarterly, NOW)['availability'] == 'not_applicable'
    monkeypatch.setattr('etf_report_continuity.PARSER_DIGEST', 'changed_code')
    assert report_continuity_status(tmp_path, announcements, quarterly, NOW)['availability'] == 'reload_required'


def test_market_projection_is_readonly_and_report_continuity_cannot_promote_current_flow_or_risk_gates(tmp_path, monkeypatch):
    import market_risk
    folder = tmp_path/'etf_announcements'; folder.mkdir()
    announcements, quarterly, _ = bound_reports(folder, monkeypatch)
    monkeypatch.setattr(market_risk, 'announcement_status', lambda *a: announcements)
    monkeypatch.setattr(market_risk, 'quarterly_status', lambda *a: quarterly)
    before = {str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob('*') if p.is_file()}
    status = market_risk.build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path/'none', manifest_path=tmp_path/'none', now=NOW)
    assert status['etf_report_continuity']['matched_etfs'] == 1
    assert status['etf_report_continuity']['corporate_actions_checked'] is False
    assert status['requested_through'] is None and status['current_risk_assessment'] == 'not_calibrated'
    assert status['node_market_comparison']['status'] == 'not_evaluated'
    assert all(row['estimated_net_subscription_yuan'] is None for row in status['etf_aggregate'].values())
    assert before == {str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob('*') if p.is_file()}
