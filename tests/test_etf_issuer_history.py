from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json

import pytest

from canonical_json import digest
import etf_issuer_history as module
from etf_issuer_history import (HistoryClient, history_status, parse_china, parse_efunds, parse_js_failure,
                                parse_nf, project, query, refresh_history, reparse_history, text_body)
from market_risk import build_market_risk_status

NOW = datetime(2026, 11, 5, 3, tzinfo=timezone.utc)
START = '2026-11-05T02:00:00+00:00'
OBSERVED = '2026-11-05T02:01:00+00:00'
COMPLETED = '2026-11-05T02:02:00+00:00'


def sign(raw):
    raw['content_digest'] = digest({key: value for key, value in raw.items() if key != 'content_digest'})


def html_china(code, empty=False):
    row = '' if empty else '<tr><td>2026</td><td>2026-09-04</td><td>0.1250</td><td>2026-09-09</td></tr>'
    return f'''<html><input name="fundcode" value="{code}"><table id="hoverBox1"><tr><th>年份</th><th>权益登记日</th><th>每份分红（元）</th><th>分红发放日</th></tr></table>
    <table id="hoverBox1_1">{row}<tr><td></td><td></td><td>合计:{'' if empty else '0.1250'}</td><td></td></tr></table>
    <script>let totalPage = '1';let currentPage = '1';</script></html>'''


def ef_payload():
    return {'status': 1, 'total': 1, 'moneyType': '元', 'showRecordDate': True, 'showPayDate': True,
            'data': [{'amtSplitType': 'BONUS', 'recordDate': '2026-08-04', 'outRecordDate': '2026-08-04',
                      'inRecordDate': '2026-08-03', 'inpayDate': '2026-08-06', 'payDate': '2026-08-05',
                      'bchDate': '2026-07-31', 'unitProfit': '0.0750'}]}


def nf_payload(code):
    def block(rows):
        return {'total': len(rows), 'list': rows, 'pageNum': 1, 'pageSize': 10, 'size': len(rows),
                'pages': 1, 'hasNextPage': False, 'nextPage': 0}
    rows = [{'f1': code, 'securitiesBo': {'f16': code}, 'f6': 1, 'f7': '0.1', 'f7f6': '0.1',
             'f8': '20260901', 'f9': '20260902', 'f10': '20260907'}]
    splits = [{'fundCode': code, 'splitDate': '20260807', 'molecular': '0.5', 'denominator': 1}]
    return {'code': 'ETS-5BP00000', 'data': {'jjfhlist': block(rows), 'splitlist': block(splits), 'sum_f7f6': '0.1'}}


@pytest.fixture
def archive(tmp_path, monkeypatch):
    directory = tmp_path/'issuer_action_history'; responses = directory/'responses'; responses.mkdir(parents=True)
    def ref(expected, body, zipped=False):
        raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        if zipped: raw = gzip.compress(raw)
        sha = hashlib.sha256(raw).hexdigest(); (responses/f'{sha}.raw').write_bytes(raw)
        url, method, params, encoding = expected
        return {'url': url, 'final_url': url, 'method': method, 'params': params, 'request_encoding': encoding,
                'content_encoding': 'gzip' if zipped else '', 'response_sha256': sha, 'bytes': len(raw), 'observed_at': OBSERVED}
    proof_texts = {
        'efunds_page': "fundCode:'510310' "+module.EF_API+' 每份红利(元) unitProfit inRecordDate outRecordDate inpayDate bchDate',
        'nf_page': '每单位基金派息(元) 权益登记日 红利发放日',
        'nf_html': 'synthetic reviewed display mapping', 'nf_request': 'synthetic reviewed query mapping', 'js_request': 'synthetic reviewed JS query mapping'}
    proofs = {key: (url, hashlib.sha256(proof_texts[key].encode()).hexdigest() if expected_hash else None)
              for key, (url, expected_hash) in module.PROOFS.items()}
    monkeypatch.setattr(module, 'PROOFS', proofs)
    ef_grammar = 'function devidend_queryData(){ synthetic reviewed dividend grammar }'
    proof_texts['efunds_page'] += ef_grammar+"$('.devidend_page').on("
    monkeypatch.setattr(module, 'EF_DIVIDEND_GRAMMAR_SHA256', hashlib.sha256(ef_grammar.encode()).hexdigest())
    raw = {'contract_version': module.VERSION, 'processor_digest': module.PROCESSOR_DIGEST, 'window_start': '2026-08-04',
           'through': '2026-11-04', 'query_cutoff': '2026-11-05', 'started_at': START, 'completed_at': COMPLETED,
           'availability_basis': 'first_observed_not_historical_PIT', 'proofs': {}, 'funds': {}}
    for key, (url, _) in proofs.items(): raw['proofs'][key] = ref((url, 'GET', None, None), proof_texts[key], zipped=key == 'nf_html')
    huatai = '''<html><script>var project = seekProject('510300');</script>
    <table>每10份基金份额分红（元） 红利发放日/再投资日<tbody id="fhTbody"><tr><td>2026</td><td>2026-08-03</td><td>2026-08-05</td><td>10.000</td></tr></tbody></table>
    <script>var allPage=$("#fhTbody>tr").length/10;showFhTable(1,allPage,10,"fenhong-page");</script></html>'''
    bodies = {'510300.SH': huatai, '510310.SH': ef_payload(), '510330.SH': html_china('510330'),
              '159919.SZ': {'error_no': '-1', 'error_info': 'synthetic upstream failure'},
              '159922.SZ': {'error_no': '-1', 'error_info': 'synthetic upstream failure'},
              '510500.SH': nf_payload('510500'), '512100.SH': nf_payload('512100'), '159845.SZ': html_china('159845', True)}
    for code, body in bodies.items(): raw['funds'][code] = [ref(query(code, raw['query_cutoff']), body)]
    sign(raw); (directory/'current.json').write_text(json.dumps(raw))
    return directory, raw, ref


def test_eight_sources_keep_valid_records_empty_table_and_upstream_errors_distinct(archive):
    directory, _, _ = archive; data = history_status(directory, NOW)
    assert (data['history_tables_observed'], data['empty_tables_unconfirmed'], data['query_failed_etfs']) == (5, 1, 2)
    funds = {row['code']: row for row in data['funds']}
    for code in ('159919.SZ', '159922.SZ'):
        assert funds[code]['availability'] == 'query_failed'
        assert funds[code]['table_records'] is funds[code]['window_record_date_count'] is None
    assert funds['159845.SZ']['availability'] == 'empty_table_unconfirmed'
    assert funds['159845.SZ']['window_cash_paid_date_count'] is None
    assert funds['510300.SH']['latest_listed_distribution']['amount_yuan_per_share'] == '1'
    assert funds['510300.SH']['latest_listed_distribution']['source_amount_text'] == '10.000'
    assert funds['510300.SH']['window_record_date_count'] == 0 and funds['510300.SH']['window_cash_paid_date_count'] == 1
    # Two markets' dates still describe one distribution, with the reference day separate.
    assert funds['510310.SH']['window_record_date_count'] == 1
    assert funds['510310.SH']['latest_listed_distribution']['evaluation_reference_on'] == '2026-07-31'
    assert all(row['window_ex_dividend_count'] is None for row in data['funds'])
    assert funds['510500.SH']['window_split_count'] == 1 and funds['510500.SH']['split_table_status'] == 'observed'
    assert all(row['corporate_actions_checked'] is False for row in data['funds'])
    assert data['corporate_actions_checked'] is False and data['estimated_net_subscription_yuan'] is None


@pytest.mark.parametrize('bad', ['query_code', 'query_window', 'query_encoding', 'bool_page', 'redirect', 'wrong_hash', 'future_time', 'naive_time', 'before_start', 'unknown_fund', 'missing_fund', 'extra_page'])
def test_rehashed_reference_cannot_change_identity_scope_query_or_observation(archive, bad):
    directory, raw, _ = archive; source = raw['funds']['510310.SH'][0]
    if bad == 'query_code': source['params']['fundCode'] = '510330'
    elif bad == 'query_window': source['params']['endDate'] = '2026-11-04'
    elif bad == 'query_encoding': source['request_encoding'] = 'form'
    elif bad == 'bool_page': source['params']['pageIndex'] = False
    elif bad == 'redirect': source['final_url'] = 'https://example.com'
    elif bad == 'wrong_hash': source['response_sha256'] = '../bad'
    elif bad == 'future_time': source['observed_at'] = '2026-11-05T04:00:00+00:00'
    elif bad == 'naive_time': source['observed_at'] = '2026-11-05T02:01:00'
    elif bad == 'before_start': source['observed_at'] = '2026-11-04T02:01:00+00:00'
    elif bad == 'unknown_fund': raw['funds']['000001.SZ'] = raw['funds'].pop('159919.SZ')
    elif bad == 'missing_fund': raw['funds'].pop('159919.SZ')
    else: raw['funds']['159845.SZ'].append(deepcopy(raw['funds']['159845.SZ'][0]))
    sign(raw); (directory/'current.json').write_text(json.dumps(raw))
    assert history_status(directory, NOW)['availability'] == 'invalid'


@pytest.mark.parametrize('field,value', [('processor_digest', '0'*64), ('availability_basis', 'historical_PIT'),
                                       ('query_cutoff', '2026-11-06'), ('through', '2026-11-05')])
def test_rehashed_global_snapshot_cannot_move_processor_or_source_dates(archive, field, value):
    directory, raw, _ = archive; raw[field] = value; sign(raw); (directory/'current.json').write_text(json.dumps(raw))
    assert history_status(directory, NOW)['availability'] == 'invalid'


def test_schema_proof_bytes_and_decoded_fingerprint_are_both_enforced(archive):
    directory, raw, ref = archive
    raw['proofs']['nf_html'] = ref((module.PROOFS['nf_html'][0], 'GET', None, None), 'changed field mapping', zipped=True)
    sign(raw); (directory/'current.json').write_text(json.dumps(raw))
    assert history_status(directory, NOW)['availability'] == 'invalid'


def test_changed_efunds_field_grammar_cannot_pass_with_the_same_keywords(archive):
    directory, raw, ref = archive; source = raw['proofs']['efunds_page']
    text = (directory/'responses'/f"{source['response_sha256']}.raw").read_text().replace('reviewed dividend grammar', 'swapped field display grammar')
    raw['proofs']['efunds_page'] = ref((module.PROOFS['efunds_page'][0], 'GET', None, None), text)
    sign(raw); (directory/'current.json').write_text(json.dumps(raw))
    assert history_status(directory, NOW)['availability'] == 'invalid'


def test_changed_archived_bytes_are_reparsed_and_not_counted_as_a_complete_table(archive):
    directory, raw, _ = archive; source = raw['funds']['510300.SH'][0]
    (directory/'responses'/f"{source['response_sha256']}.raw").write_bytes(b'<html></html>')
    assert history_status(directory, NOW)['availability'] == 'invalid'


@pytest.mark.parametrize('bad', ['wrong_fund', 'wrong_units', 'more_pages', 'sum', 'missing_total', 'duplicate', 'wrong_year'])
def test_china_identity_amount_unit_complete_pagination_and_total(bad):
    text = html_china('510330')
    if bad == 'wrong_fund': text = text.replace('510330', '159845')
    elif bad == 'wrong_units': text = text.replace('每份分红', '每10份分红')
    elif bad == 'more_pages': text = text.replace("totalPage = '1'", "totalPage = '2'")
    elif bad == 'sum': text = text.replace('合计:0.1250', '合计:0.0125')
    elif bad == 'missing_total': text = text.replace('合计:', '未知:')
    elif bad == 'duplicate': text = text.replace('<tr><td>2026', '<tr><td>2026</td><td>2026-09-04</td><td>0.1250</td><td>2026-09-09</td></tr><tr><td>2026')
    else: text = text.replace('<td>2026</td>', '<td>2025</td>')
    with pytest.raises(ValueError): parse_china(text, '510330.SH')


@pytest.mark.parametrize('bad', ['failed', 'money_unit', 'bool_total', 'incomplete', 'kind', 'scope', 'zero', 'bad_amount', 'date_order'])
def test_efunds_distinguishes_error_and_checks_count_units_dual_market_dates(bad):
    value = ef_payload()
    if bad == 'failed': value['status'] = 0
    elif bad == 'money_unit': value['moneyType'] = '万元'
    elif bad == 'bool_total': value['total'] = True
    elif bad == 'incomplete': value['total'] = 2
    elif bad == 'kind': value['data'][0]['amtSplitType'] = 'SPLIT'
    elif bad == 'scope': value['data'][0]['recordDate'] = '2026-08-03'
    elif bad == 'zero': value['data'][0]['unitProfit'] = '0'
    elif bad == 'bad_amount': value['data'][0]['unitProfit'] = 'NaN'
    else: value['data'][0]['inpayDate'] = '2026-08-01'
    with pytest.raises(ValueError): parse_efunds([value])


@pytest.mark.parametrize('bad', ['failed', 'fund', 'denominator', 'amount', 'total', 'pages', 'has_next', 'split_fund', 'split_ratio', 'split_denominator'])
def test_nf_checks_success_product_unit_dividend_sum_and_both_table_completenesses(bad):
    value = nf_payload('510500'); row = value['data']['jjfhlist']['list'][0]; split = value['data']['splitlist']['list'][0]
    if bad == 'failed': value['code'] = 'ERROR'
    elif bad == 'fund': row['securitiesBo']['f16'] = '512100'
    elif bad == 'denominator': row['f6'] = 10
    elif bad == 'amount': row['f7f6'] = '0.01'
    elif bad == 'total': value['data']['sum_f7f6'] = '0.2'
    elif bad == 'pages': value['data']['splitlist']['pages'] = 2
    elif bad == 'has_next': value['data']['jjfhlist']['hasNextPage'] = True
    elif bad == 'split_fund': split['fundCode'] = '512100'
    elif bad == 'split_ratio': split['molecular'] = 0
    else: split['denominator'] = 2
    with pytest.raises(ValueError): parse_nf(value, '510500.SH')


@pytest.mark.parametrize('value', ['0', 0, True, '-1.0', None])
def test_js_unreviewed_success_or_malformed_status_never_becomes_zero_events(value):
    with pytest.raises(ValueError): parse_js_failure({'error_no': value})


def test_nf_f9_is_not_assumed_to_be_an_ex_dividend_date():
    data = parse_nf(nf_payload('510500'), '510500.SH')
    assert data['distributions'][0]['ex_dividend_on'] is None


def test_efunds_requires_requested_page_sizes_even_if_combined_total_and_dates_are_valid():
    value = ef_payload(); records = []
    for index in range(1, 13):
        day = f'2026-08-{index:02}'
        records.append({**value['data'][0], 'inRecordDate': day, 'outRecordDate': day, 'recordDate': day,
                        'inpayDate': '2026-09-01', 'payDate': '2026-09-01'})
    pages = [{**value, 'total': 12, 'data': records[:11]}, {**value, 'total': 12, 'data': records[11:]}]
    with pytest.raises(ValueError, match='page size'): parse_efunds(pages)


def test_nf_rejects_a_large_single_page_that_disagrees_with_its_page_size():
    value = nf_payload('510500'); block = value['data']['jjfhlist']; original = block['list'][0]
    block['list'] = [{**original, 'f8': f'202609{index:02}', 'f10': '20260920'} for index in range(1, 12)]
    block.update(total=11, size=11); value['data']['sum_f7f6'] = '1.1'
    with pytest.raises(ValueError, match='pagination'): parse_nf(value, '510500.SH')


def test_gzip_decoding_is_bounded_and_unsupported_encodings_are_rejected():
    assert text_body(gzip.compress('金额单位'.encode()), 'gzip') == '金额单位'
    with pytest.raises(ValueError): text_body(b'{}', 'br')
    with pytest.raises(ValueError): text_body(gzip.compress(b'x'*8_000_001), 'gzip')


def test_network_failure_preserves_current_history_snapshot(archive):
    directory, _, _ = archive; before = (directory/'current.json').read_bytes()
    class Failed:
        def request(self, *_): raise TimeoutError('upstream detail')
    report = refresh_history(Failed(), start='2026-08-04', through='2026-11-04', output=directory, now=NOW)
    assert report == {'status': 'failed', 'reason': 'TimeoutError', 'current_snapshot_preserved': True}
    assert (directory/'current.json').read_bytes() == before


class ReplayClient:
    def __init__(self, directory, raw):
        self.response_dir = directory/'responses'
        self.refs = list(raw['proofs'].values())+[ref for group in raw['funds'].values() for ref in group]
    def request(self, url, method='GET', params=None, encoding=None):
        source = next(ref for ref in self.refs if (ref['url'], ref['method'], ref['params'], ref['request_encoding']) == (url, method, params, encoding))
        return {**source, 'observed_at': NOW.isoformat()}


def test_successful_complete_collection_keeps_known_upstream_failures_as_unknowns(archive, tmp_path):
    directory, raw, _ = archive; output = tmp_path/'published'
    report = refresh_history(ReplayClient(directory, raw), start='2026-08-04', through='2026-11-04', output=output, now=NOW)
    assert report['status'] == 'partial'
    assert (report['history_tables_observed'], report['empty_tables_unconfirmed'], report['query_failed_etfs']) == (5, 1, 2)
    data = history_status(output, NOW)
    assert len(data['funds']) == 8 and all(fund['observed_at'] == NOW.isoformat() for fund in data['funds'])


def test_previous_observed_history_is_not_erased_by_a_new_empty_table(archive):
    directory, raw, ref = archive; original = (directory/'current.json').read_bytes()
    raw['funds']['510330.SH'] = [ref(query('510330.SH', '2026-11-05'), html_china('510330', True))]
    report = refresh_history(ReplayClient(directory, raw), start='2026-08-04', through='2026-11-04', output=directory, now=NOW)
    assert report['status'] == 'failed' and report['current_snapshot_preserved'] is True
    assert (directory/'current.json').read_bytes() == original


def test_foreign_source_directory_is_not_overwritten(tmp_path):
    path = tmp_path/'current.json'; original = '{"contract_version":"another_source"}'; path.write_text(original)
    with pytest.raises(ValueError, match='another source'): refresh_history(None, start='2026-08-04', through='2026-11-04', output=tmp_path, now=NOW)
    assert path.read_text() == original


def test_explicit_archive_reparse_preserves_first_observation_times_after_code_binding_changes(archive):
    directory, raw, _ = archive; raw['processor_digest'] = '0'*64; sign(raw); (directory/'current.json').write_text(json.dumps(raw))
    assert history_status(directory, NOW)['availability'] == 'invalid'
    report = reparse_history(output=directory, start='2026-08-04', through='2026-11-04', now=NOW)
    assert report['mode'] == 'reparsed_archived_responses' and report['fetched_times_preserved'] is True
    data = history_status(directory, NOW)
    assert data['availability'] == 'partial' and data['reparsed_at'] == NOW.isoformat()
    assert data['started_at'] == START and data['completed_at'] == COMPLETED
    assert all(fund['observed_at'] == OBSERVED for fund in data['funds'])


@pytest.mark.parametrize('bad', ['raw_bytes', 'window', 'snapshot_digest'])
def test_failed_reparse_preserves_the_original_archive(archive, bad):
    directory, raw, _ = archive
    start = '2026-08-04'
    if bad == 'raw_bytes':
        (directory/'responses'/f"{raw['funds']['510300.SH'][0]['response_sha256']}.raw").write_bytes(b'bad')
    elif bad == 'window': start = '2026-09-04'
    else:
        raw['through'] = '2026-11-03'; (directory/'current.json').write_text(json.dumps(raw))
    before = (directory/'current.json').read_bytes()
    report = reparse_history(output=directory, start=start, through='2026-11-04', now=NOW)
    assert report['status'] == 'failed' and report['current_snapshot_preserved'] is True
    assert (directory/'current.json').read_bytes() == before


def test_http_api_does_not_open_cash_revision_or_risk_gates_for_source_table_checks(archive):
    directory, _, _ = archive
    data = build_market_risk_status(snapshot_dir=directory.parent, database=directory.parent/'missing.db', manifest_path=directory.parent/'missing.json', now=NOW)
    assert data['etf_issuer_history']['history_tables_observed'] == 5
    assert data['etf_issuer_history']['corporate_actions_checked'] is False
    assert all(row['estimated_net_subscription_yuan'] is None for row in data['etf_aggregate'].values())
    assert data['current_risk_assessment'] == 'not_calibrated' and data['node_market_comparison']['status'] == 'not_evaluated'


def test_collector_does_not_archive_redirected_or_undeclared_responses(tmp_path, monkeypatch):
    client = HistoryClient(tmp_path)
    with pytest.raises(ValueError): client.request('https://example.com')
    class Redirect:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def geturl(self): return 'https://example.com/redirected'
        def read(self, *_): pytest.fail('redirect content should not be read')
    monkeypatch.setattr(module, 'urlopen', lambda *_args, **_kwargs: Redirect())
    with pytest.raises(ValueError): client.request(module.PROOFS['efunds_page'][0])
    assert not list(tmp_path.iterdir())
