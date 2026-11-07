from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
from etf_quarterly import compare_daily, completed_quarter, parse_report, quarterly_status

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
CODE = "510310.SH"


def report_pages():
    return ["""2026年第3季度报告 本报告期自2026年7月1日起至9月30日止。
    本报告中财务资料未经审计。§2 基金产品概况 基金主代码510310
    报告期末基金份额总额12,031,903,922.00份""",
    """§6 开放式基金份额变动 单位：份
    报告期期初基金份额总额11,644,903,922.00
    报告期期间基金总申购份额5,370,300,000.00
    减：报告期期间基金总赎回份额4,983,300,000.00
    报告期期间基金拆分变动份额（份额减少以“-”填列）-
    报告期期末基金份额总额12,031,903,922.00
    注：期初基金总份额包含场外份额44,159,905份；期末基金总份额包含场外份额44,159,905份。
    §7 基金管理人运用固有资金投资本基金情况"""]


def test_exact_share_accounting_preserves_dashes_and_explicit_off_exchange_scope():
    result = parse_report(report_pages(), CODE, 2026, 3)
    assert result["period_start"] == "2026-07-01" and result["period_end"] == "2026-09-30"
    assert result["net_subscription_shares"] == "387000000.00"
    assert result["closing_shares"] == "12031903922.00" and result["table_page"] == 2
    assert result["off_exchange_closing_shares"] == "44159905"
    assert result["accounting_residual_shares"] == "0.00"
    assert result["split_entry"] == "-" and result["reported_split_shares"] is None
    assert result["audit_status"] == "report_states_unaudited"


@pytest.mark.parametrize("alter", ["wrong_code", "quarter", "date", "units", "product_summary", "broken_accounting", "duplicate_table", "duplicate_field", "malformed_commas", "missing_off_exchange", "negative_subscription"])
def test_ambiguous_identity_period_units_scope_or_accounting_do_not_parse(alter):
    pages = report_pages()
    if alter == "wrong_code": pages[0] = pages[0].replace('代码510310', '代码510300')
    elif alter == "quarter": pages[0] = pages[0].replace('第3季度', '第2季度')
    elif alter == "date": pages[0] = pages[0].replace('7月1日', '7月2日')
    elif alter == "units": pages[1] = pages[1].replace('单位：份', '单位：万份')
    elif alter == "product_summary": pages[0] = pages[0].replace('12,031,903,922.00', '12,031,903,923.00')
    elif alter == "broken_accounting": pages[1] = pages[1].replace('5,370,300,000.00', '5,370,300,001.00')
    elif alter == "duplicate_table": pages += [pages[1]]
    elif alter == "duplicate_field": pages[1] = pages[1].replace('报告期期初', '报告期期初基金份额总额1报告期期间基金总申购份额2报告期期初')
    elif alter == "malformed_commas": pages[1] = pages[1].replace('5,370,300,000.00', '5,37,0300,000.00')
    elif alter == "missing_off_exchange": pages[1] = pages[1].replace('期末基金总份额包含场外份额44,159,905份', '期末场外份额未列明')
    else: pages[1] = pages[1].replace('5,370,300,000.00', '-5,370,300,000.00')
    with pytest.raises(ValueError): parse_report(pages, CODE, 2026, 3)


def test_numeric_split_is_an_accounting_amount_not_a_ratio_or_current_event_clearance():
    pages = report_pages()
    pages[0] = pages[0].replace('12,031,903,922.00', '12,031,903,932.00')
    pages[1] = pages[1].replace('填列）-', '填列）10.00').replace('12,031,903,922.00', '12,031,903,932.00')
    result = parse_report(pages, CODE, 2026, 3)
    assert result["reported_split_shares"] == "10.00" and result["non_subscription_share_change"] == "10.00"
    assert result["accounting_residual_shares"] == "0.00"


def test_quarterly_net_redemptions_are_preserved_and_no_off_exchange_note_is_not_zero():
    pages = report_pages()
    pages[0] = pages[0].replace('12,031,903,922.00', '11,257,903,922.00')
    pages[1] = pages[1].replace('5,370,300,000.00', '4,983,300,000.00').replace('4,983,300,000.00\n    报告期期间基金拆分', '5,370,300,000.00\n    报告期期间基金拆分')
    pages[1] = pages[1].replace('12,031,903,922.00', '11,257,903,922.00')
    pages[1] = pages[1][:pages[1].index('注：')] + '§7 基金管理人'
    result = parse_report(pages, CODE, 2026, 3)
    assert result["net_subscription_shares"] == "-387000000.00" and result["off_exchange_closing_shares"] is None


def test_daily_comparison_keeps_scope_difference_and_exact_residual_without_rewriting_series():
    report = parse_report(report_pages(), CODE, 2026, 3)
    etf = {"source": "sse_public", "path": [{"date": "2026-09-30", "shares": 1198774.4}]}
    before = deepcopy(etf)
    result = compare_daily(report, etf)
    assert result["difference_from_report_total"] == "-44159922.00"
    assert result["difference_after_explicit_off_exchange"] == "-17.00"
    assert result["within_display_reference"] is False and result["within_reference_after_off_exchange"] is True
    assert result["source_rounding_rule"] == "not_confirmed" and etf == before
    etf['path'][0]['date'] = '2026-10-01'
    assert compare_daily(report, etf)["availability"] == "missing"
    etf['path'][0]['date'] = '2026-09-30'
    etf['path'] += etf['path']
    assert compare_daily(report, etf)["availability"] == "missing"


def test_latest_completed_quarter_never_becomes_a_two_month_or_partial_quarter_window():
    assert completed_quarter('2026-11-04') == (2026, 3, '2026-07-01', '2026-09-30')
    assert completed_quarter('2026-09-30') == (2026, 3, '2026-07-01', '2026-09-30')
    assert completed_quarter('2026-09-29') == (2026, 2, '2026-04-01', '2026-06-30')
    assert completed_quarter('2026-01-01') == (2025, 4, '2025-10-01', '2025-12-31')


def test_reader_requires_bound_capture_and_rechecks_document_bytes(tmp_path, monkeypatch):
    text = json.dumps({'pages':report_pages()}).encode(); key = hashlib.sha256(text).hexdigest()
    (tmp_path/'document_text').mkdir(); (tmp_path/'document_text'/f'{key}.json').write_bytes(text)
    document = {'document_id':'quarter','title':'2026年第3季度报告','published_on':'2026-10-27','url':'https://www.sse.com.cn/q.pdf','code':CODE}
    result = {'text_sha256':key,'format':'pdf','responses':[{'url':document['url'],'observed_at':NOW.isoformat()}]}
    capture = {'documents':{'quarter':result},'catalog_digest':'catalog','completed_at':NOW.isoformat()}
    capture['content_digest'] = digest(capture)
    (tmp_path/'document_capture.json').write_text(json.dumps(capture))
    announcements = {'availability':'observed','through':'2026-11-05','content_digest':'catalog',
                     'fulltext':{'availability':'observed','content_digest':capture['content_digest']},
                     'catalogs':[{'code':CODE,'required_documents':[document]}]}
    # The byte verifier itself has separate raw/archive tampering coverage; keep this focused on the quarterly reader's binding.
    monkeypatch.setattr('etf_quarterly.valid_ready',lambda *a:True)
    status = quarterly_status(tmp_path, announcements, [], '2026-11-04', NOW)
    assert status['observed_reports'] == 1 and status['corporate_actions_checked'] is False
    assert status['reports'][0]['net_subscription_shares'] == '387000000.00'
    for timestamp in ('2026-11-06T00:00:00+00:00','2026-10-20T00:00:00+00:00','2026-11-05T00:00:00'):
        bad=deepcopy(capture);bad['documents']['quarter']['responses'][0]['observed_at']=timestamp
        bad.pop('content_digest');bad['content_digest']=digest(bad)
        (tmp_path/'document_capture.json').write_text(json.dumps(bad))
        announcements['fulltext']['content_digest']=bad['content_digest']
        assert quarterly_status(tmp_path,announcements,[],'2026-11-04',NOW)['observed_reports']==0
    (tmp_path/'document_capture.json').write_text(json.dumps(capture))
    announcements['fulltext']['content_digest']=capture['content_digest']
    (tmp_path/'document_text'/f'{key}.json').write_bytes(text+b' ')
    assert quarterly_status(tmp_path, announcements, [], '2026-11-04', NOW)['observed_reports'] == 0
    announcements['fulltext']['content_digest'] = 'different_capture'
    assert quarterly_status(tmp_path, announcements, [], '2026-11-04', NOW)['availability'] == 'invalid'


def test_running_reader_does_not_claim_the_digest_of_new_code_it_has_not_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr('etf_quarterly.PARSER_SOURCE_DIGEST','new_code_not_loaded')
    assert quarterly_status(tmp_path, {}, [], '2026-11-04', NOW)['availability'] == 'reload_required'
