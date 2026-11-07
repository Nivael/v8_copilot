from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
import market_breadth_combined as m

NOW = datetime(2026, 11, 5, 8, tzinfo=timezone.utc)


def stop(code, start='20260904', end='', **kwargs):
    return {'productCode': code, 'startStopDate': start, 'endStopDate': end, 'type': 'LXTP', 'stopTime': '',
            'controlType': 'TR', 'stopReason': '重要公告', 'endStopReason': '' if not end else '重要公告',
            'productName': '样本' + code, **kwargs}


@pytest.fixture
def capture(tmp_path, monkeypatch):
    rows = [stop('688121'), stop('688496'), stop('113001', controlType='GB')]
    refs = []
    for kind in ['stock_page', 'trade_tip', 'all', '688121', '688496']:
        ref = {'kind': kind, 'observed_at': '2026-11-05T07:00:00+00:00'}
        if kind == 'stock_page':
            data = b'<div class="js_suspension_stock"></div>'; ref['url'] = m.SOURCE_URL
        elif kind == 'trade_tip':
            data = "suspensionUrl: sseQueryURL + 'commonSoaQuery.do'; 'GW_PL_JYTS_TFPXX'; value == 'WH'; return '全天'".encode()
            ref['url'] = m.SCRIPT_URL
        else:
            selected = rows if kind == 'all' else [r for r in rows if r['productCode'] == kind]
            data = json.dumps({'sqlId': 'GW_PL_JYTS_TFPXX', 'actionErrors': [], 'fieldErrors': {}, 'isPagination': 'true',
                               'result': selected, 'pageHelp': {'data': selected, 'total': len(selected), 'pageNo': 1, 'pageSize': 100, 'pageCount': 1}}).encode()
            ref.update(url=m.API, params=m.query_params('' if kind == 'all' else kind))
        sha = hashlib.sha256(data).hexdigest(); (tmp_path / (sha + '.raw')).write_bytes(data)
        refs.append({**ref, 'sha256': sha, 'bytes': len(data)})
    raw = {'version': 'sse_suspend_interval_capture_v1', 'start': m.PLAN['start'], 'through': m.PLAN['through'], 'source_refs': refs}
    (tmp_path / 'complete.json').write_text(json.dumps(raw))
    monkeypatch.setitem(m.PLAN, 'suspension_capture', digest(raw))
    return tmp_path


def revise(capture, modify, kind='all'):
    path = capture / 'complete.json'; raw = json.loads(path.read_text()); ref = next(r for r in raw['source_refs'] if r['kind'] == kind)
    payload = json.loads((capture / (ref['sha256'] + '.raw')).read_bytes())
    modify(payload, ref)
    data = json.dumps(payload).encode(); sha = hashlib.sha256(data).hexdigest(); (capture / (sha + '.raw')).write_bytes(data)
    ref.update(sha256=sha, bytes=len(data)); path.write_text(json.dumps(raw)); m.PLAN['suspension_capture'] = digest(raw)


def test_reads_the_current_interface_and_cross_checks_unfiltered_and_security_queries(capture):
    rows, refs = m.read_suspensions(capture, NOW)
    assert len(rows) == 3 and len(refs) == 5
    assert {r['productCode'] for r in rows} == {'688121', '688496', '113001'}


@pytest.mark.parametrize('damage', ['filter', 'old_api', 'old_sql', 'errors', 'page_gap', 'truncated', 'different_page_data',
                                   'duplicate', 'individual_mismatch', 'foreign_individual', 'premature', 'raw_bytes'])
def test_rejects_unverified_scope_paging_bytes_chronology_and_individual_lookup_disagreement(capture, damage):
    def change(j, r):
        if damage == 'filter': r['params']['keyWords'] = '停牌'
        elif damage == 'old_api': r['url'] = 'https://query.sse.com.cn/sseQuery/commonQuery.do'
        elif damage == 'old_sql': j['sqlId'] = 'COMMON_SSE_XXPL_JYTS_TFPXX_L'
        elif damage == 'errors': j['actionErrors'] = ['unavailable']
        elif damage == 'page_gap': j['pageHelp']['pageCount'] = 2; j['pageHelp']['total'] = 101
        elif damage == 'truncated': j['pageHelp']['total'] += 1
        elif damage == 'different_page_data': j['pageHelp']['data'] = []
        elif damage == 'duplicate': j['result'][2] = deepcopy(j['result'][0]); j['pageHelp']['data'] = j['result']
        elif damage == 'individual_mismatch': j['result'][0]['endStopDate'] = '20261103'; j['pageHelp']['data'] = j['result']
        elif damage == 'foreign_individual': j['result'][0]['productCode'] = '600001'; j['pageHelp']['data'] = j['result']
        elif damage == 'premature': r['observed_at'] = '2026-11-04T06:00:00+00:00'
    if damage == 'raw_bytes':
        raw = json.loads((capture / 'complete.json').read_text()); ref = next(r for r in raw['source_refs'] if r['kind'] == 'all')
        (capture / (ref['sha256'] + '.raw')).write_bytes(b'changed')
    else: revise(capture, change, '688121' if damage == 'foreign_individual' else 'all')
    with pytest.raises(ValueError): m.read_suspensions(capture, NOW)


@pytest.fixture
def intervals():
    calendar = ['2026-09-04', '2026-09-07', '2026-09-08']
    codes = ['600001', '600002', '600003', '688121', '688496']
    rows = [stop('600001', end='20260907'), stop('600002', start='20260908', end='20260908', type='LSTP', stopTime='WH'),
            stop('600003', start='20260907', end='20260907', type='LSTP', stopTime='AM'),
            stop('688121', start='20260908'), stop('688496'), stop('113001', controlType='GB')]
    basis = {'pool': dict.fromkeys(codes), 'window': {'calendar': calendar}, 'populations': {d: codes for d in calendar}}
    endpoints = {'688121': {'is_trading': False}, '688496': {'is_trading': False}}
    notices = {'episodes': [{'kind': 'start_only', 'symbol': '688121', 'start_on': '2026-09-08'},
                            {'kind': 'start_only', 'symbol': '688496', 'start_on': '2026-09-04'}],
               'days': [{'date': '2026-09-04', 'confirmed_suspended': ['600001.SH']},
                        {'date': '2026-09-07', 'confirmed_suspended': ['600001.SH']},
                        {'date': '2026-09-08', 'confirmed_suspended': ['600002.SH']}]}
    return rows, basis, endpoints, notices


def test_inclusive_last_stop_date_open_continuity_and_intraday_are_separate(intervals):
    pairs, report = m.suspension_days(*intervals)
    assert len(pairs) == 7 and ('2026-09-07', '600001') in pairs and ('2026-09-08', '600001') not in pairs
    assert ('2026-09-07', '600003') not in pairs
    assert report['ordinary_A_records'] == 4 and report['excluded'] == {'intraday': 1, 'other_securities_or_business': 1}
    assert (report['notice_confirmed_days'], report['additional_continuous_days']) == (3, 4)


@pytest.mark.parametrize('damage', ['start_mismatch', 'endpoint_traded', 'end_reason', 'backwards', 'unknown_type',
                                   'temporary_range', 'continuous_intraday', 'overlap', 'foreign_stock', 'notice_conflict'])
def test_open_or_closed_intervals_cannot_override_identity_dates_and_notice_evidence(intervals, damage):
    rows, basis, endpoint, notice = intervals
    if damage == 'start_mismatch': notice['episodes'][0]['start_on'] = '2026-09-07'
    elif damage == 'endpoint_traded': endpoint['688121']['is_trading'] = True
    elif damage == 'end_reason': rows[3]['endStopReason'] = '已复牌'
    elif damage == 'backwards': rows[0]['endStopDate'] = '20260903'
    elif damage == 'unknown_type': rows[0]['type'] = 'UNKNOWN'
    elif damage == 'temporary_range': rows[1]['startStopDate'] = '20260907'
    elif damage == 'continuous_intraday': rows[0]['stopTime'] = 'AM'
    elif damage == 'overlap': rows.append(deepcopy(rows[0]))
    elif damage == 'foreign_stock': rows[0]['productCode'] = '600009'
    else: notice['days'][0]['confirmed_suspended'] = ['600003.SH']
    with pytest.raises(ValueError): m.suspension_days(rows, basis, endpoint, notice)


def quote(code, last, previous, **kwargs):
    return {'ts_code': code, 'last': str(last), 'prev_close': str(previous), 'pct_chg': (last/previous-1)*100,
            'amount': 1000, 'is_trading': True, **kwargs}


def test_merges_security_denominators_not_venue_percentages_and_never_fills_halted_prices():
    a = [quote('600001.SH', 9, 10), quote('600002.SH', 95, 100), {'ts_code': '600003.SH', 'is_trading': False}]
    b = [quote('000001.SZ', 10, 10)]
    result = m.summarize_day('2026-09-04', a, b)
    assert result['SSE']['declining_share_pct'] == 100 and result['SZSE']['declining_share_pct'] == 0
    assert result['all']['declining_share_pct'] == 66.666667  # Not the average 50%.
    assert result['all']['nontrading_stocks'] == 1 and result['all']['flat'] == 1
    assert result['all']['declining_5pct_or_more'] == 2
    assert 'last' not in a[-1]
    with pytest.raises(ValueError): m.summarize_day('2026-09-04', a + [a[0]], b)


def test_complete_materialization_rechecks_inputs_and_preserves_current(capture, tmp_path, monkeypatch):
    dates = m.sse.recent_calendar_window(m.PLAN['through'])['calendar']
    point = m.summarize_day(dates[0], [quote('600001.SH', 9, 10)], [quote('000001.SZ', 10, 10)])
    raw = json.loads((capture/'complete.json').read_text())
    data = {'points': [{**point, 'date': d} for d in dates], 'suspensions': {}, 'source_refs': raw['source_refs'],
            'first_suspension_observed_at': '2026-11-05T07:00:00+00:00', 'fetched_at': '2026-11-05T07:00:00+00:00',
            'sse_price_fetched_at': '2026-11-05T05:00:00+00:00', 'szse_fetched_at': '2026-11-05T00:00:00+00:00'}
    monkeypatch.setattr(m, 'collect_inputs', lambda *args, **kwargs: deepcopy(data))
    output = tmp_path/'published'; m.materialize(capture, output=output, now=NOW)
    assert m.history_status(output, now=NOW)['complete_market_history'] is True
    before = (output/'current.json').read_bytes(); data['points'].pop()
    assert m.history_status(output, now=NOW)['availability'] == 'invalid'
    with pytest.raises(ValueError): m.materialize(capture, output=output, now=NOW)
    assert (output/'current.json').read_bytes() == before


def test_combined_market_coverage_does_not_promote_ST_or_risk_weights(tmp_path, monkeypatch):
    import market_risk
    fake = {'availability': 'observed', 'covered_venues': ['SSE', 'SZSE'], 'through': None,
            'complete_market_history': True, 'historical_ST_ready': False, 'effect_measured': False, 'points': []}
    monkeypatch.setattr(market_risk, 'combined_breadth_status', lambda *args, **kwargs: deepcopy(fake))
    # A missing target is not a matching market date.
    result = market_risk.build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path/'missing.db', manifest_path=tmp_path/'missing.json', now=NOW)
    assert result['market_coverage']['historical_breadth_venues_at_target'] == 0
    assert result['market_coverage']['st_style_at_target'] is False and result['parameters']['risk_weights'] is None
    fake['through'] = '2026-11-04'
    monkeypatch.setattr(market_risk, '_public_indices', lambda *args, **kwargs: (
        {'availability': 'observed', 'through': '2026-11-04', 'content_digest': 'test'},
        [{'code': '000985.CSI', 'through': '2026-11-04', 'historical_only': False, 'observation_count': 61}]))
    result = market_risk.build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path/'missing.db', manifest_path=tmp_path/'missing.json', now=NOW)
    assert result['market_coverage']['historical_breadth_venues_at_target'] == 2
    assert result['market_coverage']['st_style_at_target'] is False and result['node_market_comparison']['status'] == 'not_evaluated'
    row = next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path, now=NOW) if r['source_id'] == 'combined_breadth_history')
    assert row['series_at_target'] == 2 and row['declared_series'] == 2 and row['observation_unit'] == '股票日'
