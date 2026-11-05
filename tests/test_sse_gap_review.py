from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

import sse_gap_review as m

NOW = datetime(2026, 11, 5, 7, tzinfo=timezone.utc)


@pytest.fixture
def inputs(monkeypatch):
    calendar = ['2026-09-04', '2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10']
    documents, episodes = {}, []

    def episode(code, kind, start, end):
        company = '样本公司' + code
        token = lambda d: f'{int(d[:4])}年{int(d[5:7])}月{int(d[8:])}日'
        quote = '公司股票自' + token(start) + '开市起停牌'
        if kind == 'one_day': quote = '公司股票将于' + token(start) + '停牌一日'
        claims = [{'document_id': code, 'pages': [1], 'role': 'halt_start', 'effective_on': start, 'date_text': token(start), 'quote': quote}]
        if kind == 'resumed':
            claims.append({'document_id': code, 'pages': [1], 'role': 'resume', 'effective_on': end,
                           'date_text': token(end), 'quote': '公司股票将于' + token(end) + '开市起复牌'})
        elif kind == 'continuous_to_listing_end':
            claims.append({'document_id': code, 'pages': [1], 'role': 'continuous_until_listing_end', 'quote': '公司A股股票继续停牌直至终止上市。'})
        documents[code] = {'symbol': code, 'company': company, 'pages': ['。'.join(c['quote'] for c in claims)],
                           'observed_at': '2026-11-05T06:00:00+00:00', 'published_on': '2026-09-10',
                           'source_url': 'https://static.cninfo.com.cn/finalpage/2026-09-10/123.PDF'}
        episodes.append({'case_id': code + start, 'symbol': code, 'company': company, 'kind': kind,
                         'start_on': start, 'end_exclusive': end, 'claims': claims})

    episode('600001', 'resumed', calendar[0], calendar[3])
    episode('600002', 'continuous_to_listing_end', calendar[1], calendar[4])
    episode('600003', 'one_day', calendar[1], calendar[2])
    episode('688001', 'start_only', calendar[2], None)
    populations = {d: [e['symbol'] for e in episodes if e['symbol'] != '600002' or d < calendar[4]] for d in calendar}
    prices, missing = {}, set()
    for e in episodes:
        prices[e['symbol']] = {}
        for d, codes in populations.items():
            if e['symbol'] not in codes: continue
            halted = e['start_on'] <= d and (e['end_exclusive'] is None or d < e['end_exclusive'])
            if halted: missing.add((d, e['symbol']))
            else: prices[e['symbol']][d] = {'is_trading': True}
    profile = {'episodes': episodes, 'documents': documents, 'archive_digest': 'frozen'}
    monkeypatch.setattr(m, 'PROFILE', profile)
    return {'archive': {'start': calendar[0], 'through': calendar[-1], 'days': [
        {'date': d, 'not_returned': sorted(c + '.SH' for day, c in missing if day == d), 'explicit_nontrading': []} for d in calendar]},
        'basis': {'pool': {e['symbol']: {'ended_on': calendar[4] if e['symbol'] == '600002' else None} for e in episodes},
                  'window': {'calendar': calendar}, 'populations': populations}, 'prices': prices,
        'documents': documents, 'endpoint': {'688001': {'is_trading': False}}}


def test_closed_intervals_and_start_only_evidence_remain_distinct(inputs):
    result = m.project(inputs)
    assert result['availability'] == 'partial'
    assert (result['reviewed_episodes'], result['closed_episodes'], result['not_returned_days']) == (4, 3, 10)
    assert (result['confirmed_missing_days'], result['unresolved_missing_days'], result['unreviewed_missing_days']) == (7, 3, 0)
    assert result['historical_breadth_ready'] is result['historical_ST_ready'] is result['historical_PIT'] is result['effect_measured'] is False
    ended = next(e for e in result['episodes'] if e['symbol'] == '600002')
    assert ended['end_exclusive'] == '2026-09-10' and '2026-09-10' not in ended['window_days']
    assert all(d['unresolved'] == (['688001.SH'] if d['date'] >= '2026-09-08' else []) for d in result['days'])
    assert 'daily_return' not in result  # Explaining a missing day never invents a zero return.


@pytest.mark.parametrize('damage', ['traded_inside', 'resume_missing', 'resume_inactive', 'listing_end', 'endpoint_active',
                                   'open_asserted_end', 'overlap', 'unknown_kind', 'empty_interval', 'wrong_one_day'])
def test_rejects_conflicting_prices_boundaries_and_interval_categories(inputs, damage):
    if damage == 'traded_inside': inputs['prices']['600001']['2026-09-07'] = {'is_trading': True}
    elif damage == 'resume_missing': inputs['prices']['600001'].pop('2026-09-09')
    elif damage == 'resume_inactive': inputs['prices']['600001']['2026-09-09']['is_trading'] = False
    elif damage == 'listing_end': inputs['basis']['pool']['600002']['ended_on'] = None
    elif damage == 'endpoint_active': inputs['endpoint']['688001']['is_trading'] = True
    elif damage == 'open_asserted_end': m.PROFILE['episodes'][-1]['end_exclusive'] = '2026-09-11'
    elif damage == 'overlap': m.PROFILE['episodes'].append(deepcopy(m.PROFILE['episodes'][0]))
    elif damage == 'unknown_kind': m.PROFILE['episodes'][0]['kind'] = 'expected_resume'
    elif damage == 'empty_interval': inputs['basis']['populations'] = {d: [] for d in inputs['basis']['populations']}
    else: m.PROFILE['episodes'][2]['end_exclusive'] = '2026-09-09'
    with pytest.raises(ValueError): m.project(inputs)


@pytest.mark.parametrize('damage', ['forecast', 'negated_resume', 'intraday', 'foreign_date', 'wrong_company', 'wrong_symbol',
                                   'wrong_page', 'noncontiguous_pages', 'different_quote', 'continuous_direction'])
def test_requires_the_reviewed_company_physical_page_and_actual_date_role(inputs, damage):
    item = m.PROFILE['episodes'][0]
    claim = item['claims'][0]
    if damage == 'forecast': claim['quote'] = '预计' + claim['quote']
    elif damage == 'intraday': claim['quote'] = '盘中' + claim['quote']
    elif damage == 'negated_resume': claim = item['claims'][1]; claim['quote'] = '不再' + claim['quote']
    elif damage == 'foreign_date': claim['effective_on'] = '2026-09-07'
    elif damage == 'wrong_company': inputs['documents']['600001']['company'] = '另一家公司'
    elif damage == 'wrong_symbol': inputs['documents']['600001']['symbol'] = '600009'
    elif damage == 'wrong_page': claim['pages'] = [2]
    elif damage == 'noncontiguous_pages': claim['pages'] = [1, 3]
    elif damage == 'different_quote': claim['quote'] = '不存在的公告句子'
    else:
        item = m.PROFILE['episodes'][1]; claim = item['claims'][1]; claim['quote'] = '公司股票预计停牌直至终止上市。'
    if damage in ('forecast', 'intraday', 'negated_resume', 'continuous_direction'):
        inputs['documents'][claim['document_id']]['pages'][0] += claim['quote']
    with pytest.raises(ValueError): m.project(inputs)


def test_unreviewed_gaps_are_retained_in_the_total(inputs):
    m.PROFILE['episodes'].pop()
    result = m.project(inputs)
    assert result['unreviewed_missing_days'] == result['unresolved_missing_days'] == 3
    assert result['not_returned_days'] == 10 and result['historical_breadth_ready'] is False


def test_cross_page_clause_retains_printed_page_number_and_page_order(inputs):
    item = m.PROFILE['episodes'][0]; claim = item['claims'][0]
    claim.update(pages=[1, 2], quote='公司股票自2026年9月4日（星期2五）开市起停牌')
    inputs['documents']['600001']['pages'] = ['公司股票自2026年9月4日（星期', '2五）开市起停牌' + item['claims'][1]['quote']]
    item['claims'][1]['pages'] = [2]
    assert m.project(inputs)['confirmed_missing_days'] == 7
    claim['pages'] = [2, 1]
    with pytest.raises(ValueError): m.project(inputs)


def test_original_and_text_hashes_are_checked_independently(tmp_path, monkeypatch):
    raw = b'%PDF-a-test-source'; text = json.dumps({'pages': ['证券代码：600001样本公司']}, ensure_ascii=False).encode()
    sha = lambda b: hashlib.sha256(b).hexdigest()
    ref = {'raw_sha256': sha(raw), 'text_sha256': sha(text), 'raw_bytes': len(raw), 'text_bytes': len(text), 'page_count': 1,
           'source_url': 'https://static.cninfo.com.cn/finalpage/2026-09-10/123.PDF',
           'final_url': 'https://static.cninfo.com.cn/finalpage/2026-09-10/123.PDF', 'published_on': '2026-09-10',
           'observed_at': '2026-11-05T06:00:00+00:00', 'symbol': '600001', 'company': '样本公司'}
    monkeypatch.setattr(m, 'PROFILE', {'documents': {'test': ref}})
    rawpath = tmp_path / (sha(raw) + '.pdf'); textpath = tmp_path / (sha(text) + '.json')
    rawpath.write_bytes(raw); textpath.write_bytes(text)
    assert m.read_documents(tmp_path, NOW)['test']['pages'] == ['证券代码：600001样本公司']
    rawpath.write_bytes(b'changed')
    with pytest.raises(ValueError): m.read_documents(tmp_path, NOW)
    rawpath.write_bytes(raw); textpath.write_bytes(b'changed')
    with pytest.raises(ValueError): m.read_documents(tmp_path, NOW)
    textpath.write_bytes(text); ref['observed_at'] = '2026-11-06T06:00:00+00:00'
    with pytest.raises(ValueError): m.read_documents(tmp_path, NOW)


def test_publication_and_reads_preserve_current_on_invalid_changed_inputs(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'collect_inputs', lambda **kwargs: inputs)
    m.materialize(output=tmp_path, now=NOW)
    before = (tmp_path / 'current.json').read_bytes()
    assert m.review_status(tmp_path, now=NOW)['availability'] == 'partial'
    inputs['prices']['600001']['2026-09-07'] = {'is_trading': True}
    assert m.review_status(tmp_path, now=NOW)['availability'] == 'invalid'
    with pytest.raises(ValueError): m.materialize(output=tmp_path, now=NOW)
    assert (tmp_path / 'current.json').read_bytes() == before


def test_market_and_learning_observe_partial_review_without_promoting_coverage(inputs, tmp_path, monkeypatch):
    import market_risk
    result = m.project(inputs)
    monkeypatch.setattr(market_risk, 'sse_gap_review_status', lambda *args, **kwargs: deepcopy(result))
    status = market_risk.build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path/'missing.db', manifest_path=tmp_path/'missing.json', now=NOW)
    assert status['sse_gap_review']['unresolved_missing_days'] == 3
    assert status['market_coverage']['historical_breadth_venues_at_target'] == 0
    assert status['market_coverage']['st_style_at_target'] is False and status['parameters']['risk_weights'] is None
    row = next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path, now=NOW) if r['source_id'] == 'sse_missing_day_review')
    assert row['availability'] == 'partial' and row['observation_count'] == 7
    assert row['series_at_target'] is None and row['observed_source_groups'] == 3 and row['declared_series'] == 4
    assert row['coverage_basis'] == 'missing_day_episodes' and row['observation_unit'] == '已解释的缺失股票日'


def test_reload_guard_also_checks_for_a_code_change_during_a_read(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'collect_inputs', lambda **kwargs: inputs)
    m.materialize(output=tmp_path, now=NOW)
    calls = iter([m.PROCESSOR, 'changed'])
    monkeypatch.setattr(m, 'processor_digest', lambda: next(calls))
    assert m.review_status(tmp_path, now=NOW)['availability'] == 'reload_required'


def test_foreign_output_is_preserved(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'collect_inputs', lambda **kwargs: inputs)
    path = tmp_path / 'current.json'; path.write_text('{"version":"someone_else"}')
    before = path.read_bytes()
    with pytest.raises(ValueError, match='foreign'): m.materialize(output=tmp_path, now=NOW)
    assert path.read_bytes() == before
