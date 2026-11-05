from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
import combined_st_reference as m

NOW = datetime(2026, 11, 5, 9, tzinfo=timezone.utc)
DAYS = ['2026-09-04', '2026-09-07', '2026-09-08']


def row(code, change=0, active=True):
    return {'ts_code': code, 'last': str(10 * (1 + change / 100)), 'prev_close': '10', 'is_trading': active}


@pytest.fixture
def inputs(monkeypatch):
    monkeypatch.setitem(m.PLAN, 'start', DAYS[0]); monkeypatch.setitem(m.PLAN, 'through', DAYS[-1])
    monkeypatch.setattr(m.sse, 'recent_calendar_window', lambda _: {'calendar': DAYS})
    return {'calendar': DAYS, 'anchor': [{'ts_code': '600001.SH', 'name': 'ST甲'}, {'ts_code': '600002.SH', 'name': 'ST乙'}],
            'events': [{'symbol': '600003', 'kind': 'warning_added', 'effective_on': DAYS[1], 'old_name': '丙', 'new_name': 'ST丙'},
                       {'symbol': '600002', 'kind': 'warning_removed', 'effective_on': DAYS[2], 'old_name': 'ST乙', 'new_name': '乙'}],
            'sse_populations': {d: ['600001', '600002', '600003'] for d in DAYS},
            'sse_prices': {'600001': {d: row('600001.SH', 10) for d in DAYS},
                           '600002': {d: row('600002.SH', -10 if d != DAYS[2] else -90) for d in DAYS},
                           '600003': {d: row('600003.SH') for d in DAYS}},
            'szse_days': [{'date': d, 'source_marked': ['000001.SZ'], 'rows': [row('000001.SZ', 20)]} for d in DAYS],
            'sse_endpoint_members': ['600001.SH', '600003.SH'], 'confirmed_sse_suspensions': {d: [] for d in DAYS},
            'szse_reference': {'distinct_members': 1, 'endpoint_members': 1, 'reviewed_transitions': 0},
            'endpoint_list_observed_on': '2026-09-09', 'catalog': {'items': [], 'full_body_review': False},
            'sse_price_fetched_at': NOW.isoformat(), 'szse_price_fetched_at': NOW.isoformat(), 'newest_notice_observed_at': NOW.isoformat()}


def test_effective_members_and_individual_weighting_define_changing_sample_reference(inputs):
    result = m.project(inputs)
    assert result['availability'] == 'reconstructed'
    assert [p['SSE']['member_count'] for p in result['points']] == [2, 3, 2]
    assert [p['all']['daily_return_pct'] for p in result['points']] == pytest.approx([20/3, 5, 10])
    # Two flat SSE members plus one rising SZSE member is 6.67%, not a 10% average of venue means.
    assert result['points'][0]['all']['daily_return_pct'] != 10
    assert result['memberships'][1]['SSE'] == ['600001.SH', '600002.SH', '600003.SH']
    assert '600002.SH' not in result['memberships'][2]['SSE']
    assert result['metrics']['all']['return_pct'] == pytest.approx(15.5)
    assert result['metrics']['SSE']['member_day_observations'] == 7
    assert result['sse_distinct_members'] == 3 and result['sse_endpoint_members'] == 2
    assert result['verified_daily_membership_venues'] == ['SZSE']
    for flag in ('combined_ST_ready', 'historical_membership_verified', 'historical_PIT', 'portfolio_wealth', 'effect_measured'):
        assert result[flag] is False


@pytest.mark.parametrize('bad', ['calendar', 'outside', 'duplicate_event', 'unknown_event', 'old_name', 'new_name',
                                 'add_existing', 'endpoint', 'unlisted', 'missing_unexplained', 'duplicate_price', 'duplicate_member', 'bad_price'])
def test_inconsistent_members_dates_prices_and_suspensions_cannot_publish(inputs, bad):
    if bad == 'calendar': inputs['szse_days'][1]['date'] = DAYS[0]
    elif bad == 'outside': inputs['events'][0]['effective_on'] = '2026-09-09'
    elif bad == 'duplicate_event': inputs['events'].append(deepcopy(inputs['events'][0]))
    elif bad == 'unknown_event': inputs['events'][0]['kind'] = 'application_only'
    elif bad == 'old_name': inputs['events'][1]['old_name'] = 'ST其他'
    elif bad == 'new_name': inputs['events'][0]['new_name'] = '其他'
    elif bad == 'add_existing': inputs['events'][0]['symbol'] = '600001'
    elif bad == 'endpoint': inputs['sse_endpoint_members'].append('600002.SH')
    elif bad == 'unlisted': inputs['sse_populations'][DAYS[0]].remove('600002')
    elif bad == 'missing_unexplained': inputs['sse_prices']['600001'].pop(DAYS[0])
    elif bad == 'duplicate_price': inputs['szse_days'][0]['rows'] *= 2
    elif bad == 'duplicate_member': inputs['szse_days'][0]['source_marked'] *= 2
    else: inputs['sse_prices']['600001'][DAYS[0]]['prev_close'] = 'NaN'
    with pytest.raises(ValueError): m.project(inputs)


@pytest.mark.parametrize('venue', ['SSE', 'SZSE'])
def test_any_venue_late_day_coverage_failure_withholds_all_paths_without_zero_filling(inputs, venue):
    if venue == 'SSE':
        inputs['sse_prices']['600001'].pop(DAYS[-1]); inputs['confirmed_sse_suspensions'][DAYS[-1]] = ['600001.SH']
    else: inputs['szse_days'][-1]['rows'][0]['is_trading'] = False
    result = m.project(inputs)
    assert result['availability'] == 'insufficient_coverage' and len(result['points']) == 3
    assert all(p[g]['close'] is None for p in result['points'] for g in ('all', 'SSE', 'SZSE'))
    assert all(v['return_pct'] is v['max_drawdown_pct'] is None for v in result['metrics'].values())
    if venue == 'SSE':
        assert result['points'][-1]['SSE']['daily_return_pct'] == 0
        assert result['points'][-1]['SSE']['member_count'] == 2 and result['points'][-1]['SSE']['observed_members'] == 1
        assert result['points'][-1]['SSE']['missing_symbols'] == ['600001.SH']


def test_each_venue_must_meet_inclusive_95_percent_not_just_combined_coverage(inputs):
    codes = [f'600{n:03}' for n in range(1, 21)]
    inputs['anchor'] = [{'ts_code': c+'.SH', 'name': 'ST样本'} for c in codes]; inputs['events'] = []
    inputs['sse_endpoint_members'] = [c+'.SH' for c in codes]
    inputs['sse_populations'] = {d: codes for d in DAYS}
    inputs['sse_prices'] = {c: {d: row(c+'.SH', active=i>0) for d in DAYS} for i,c in enumerate(codes)}
    inputs['confirmed_sse_suspensions'] = {d: [codes[0]+'.SH'] for d in DAYS}
    assert m.project(inputs)['availability'] == 'reconstructed'
    inputs['sse_prices'][codes[1]][DAYS[-1]]['is_trading'] = False
    inputs['confirmed_sse_suspensions'][DAYS[-1]].append(codes[1]+'.SH')
    # Lots of SZSE observations cannot hide a failed SSE denominator.
    inputs['szse_days'][-1] = {'date': DAYS[-1], 'source_marked': [f'{n:06}.SZ' for n in range(100)],
                             'rows': [row(f'{n:06}.SZ') for n in range(100)]}
    data = m.project(inputs)
    assert data['points'][-1]['all']['coverage_ratio'] > .95 and data['availability'] == 'insufficient_coverage'


def test_snapshot_recomputes_ignores_injected_report_and_never_promotes_certification(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'collect_inputs', lambda **_: deepcopy(inputs)); m.materialize(output=tmp_path, now=NOW)
    path = tmp_path/'current.json'; raw = json.loads(path.read_text())
    raw['report'] = {'availability': 'observed', 'historical_membership_verified': True, 'combined_ST_ready': True}
    raw['content_digest'] = digest({k:v for k,v in raw.items() if k != 'content_digest'}); path.write_text(json.dumps(raw))
    before = path.read_bytes(); status = m.reference_status(tmp_path, now=NOW)
    assert status['availability'] == 'reconstructed' and status['historical_membership_verified'] is status['combined_ST_ready'] is False
    assert path.read_bytes() == before
    inputs['newest_notice_observed_at'] = 'changed'
    assert m.reference_status(tmp_path, now=NOW)['availability'] == 'invalid' and path.read_bytes() == before


def test_source_race_code_race_and_foreign_output_preserve_current(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'collect_inputs', lambda **_: deepcopy(inputs)); m.materialize(output=tmp_path, now=NOW)
    path = tmp_path/'current.json'; before = path.read_bytes()
    changed = deepcopy(inputs); changed['catalog']['items'] = ['changed']; seq = iter([inputs, changed])
    monkeypatch.setattr(m, 'collect_inputs', lambda **_: next(seq))
    with pytest.raises(ValueError, match='sources or code changed'): m.materialize(output=tmp_path, now=NOW)
    assert path.read_bytes() == before
    monkeypatch.setattr(m, 'collect_inputs', lambda **_: deepcopy(inputs)); seq = iter([m.PROCESSOR, 'changed'])
    monkeypatch.setattr(m, 'processor_digest', lambda: next(seq))
    with pytest.raises(ValueError, match='sources or code changed'): m.materialize(output=tmp_path, now=NOW)
    assert path.read_bytes() == before
    monkeypatch.setattr(m, 'processor_digest', lambda: m.PROCESSOR)
    path.write_text('{"version":"foreign"}'); before = path.read_bytes()
    with pytest.raises(ValueError, match='foreign'): m.materialize(output=tmp_path, now=NOW)
    assert path.read_bytes() == before


@pytest.fixture
def proof(tmp_path, monkeypatch):
    raw = b'%PDF-synthetic-test-only'
    text = json.dumps({'pages': ['证券代码：600001证券简称：甲甲股份有限公司股票简称：由“甲”变更为“ST甲”。实施其他风险警示的起始日：2026年9月8日']}, ensure_ascii=False).encode()
    item = {'symbol': '600001', 'company': '甲股份有限公司', 'old_name': '甲', 'new_name': 'ST甲', 'kind': 'warning_added',
            'effective_on': '2026-09-08', 'published_on': '2026-09-07', 'source_url': 'https://static.cninfo.com.cn/finalpage/2026-09-07/123.PDF',
            'date_label': '实施其他风险警示的起始日', 'page_count': 1, 'proof_page': 1, 'observed_at': NOW.isoformat(),
            'raw_sha256': hashlib.sha256(raw).hexdigest(), 'text_sha256': hashlib.sha256(text).hexdigest(), 'raw_bytes': len(raw), 'text_bytes': len(text)}
    (tmp_path/(item['raw_sha256']+'.pdf')).write_bytes(raw); (tmp_path/(item['text_sha256']+'.json')).write_bytes(text)
    monkeypatch.setattr(m, 'EVENTS', [item]); return tmp_path, item


def test_original_date_role_name_direction_and_chinese_publication_day_are_bound(proof):
    folder, item = proof
    item['observed_at'] = '2026-09-06T17:00:00+00:00'  # September 7 in China, before UTC midnight.
    assert m.sse_proofs(folder, NOW)[0]['effective_on'] == '2026-09-08'


@pytest.mark.parametrize('bad', ['pdf_bytes', 'text_bytes', 'code', 'company', 'date_role', 'effective', 'direction', 'kind', 'future', 'publication', 'url'])
def test_proofs_reject_metadata_or_evidence_rebinding(proof, bad):
    folder, item = proof
    if bad == 'pdf_bytes': (folder/(item['raw_sha256']+'.pdf')).write_bytes(b'%PDF-modified')
    elif bad == 'text_bytes': (folder/(item['text_sha256']+'.json')).write_bytes(b'{}')
    elif bad == 'code': item['symbol'] = '600002'
    elif bad == 'company': item['company'] = '乙股份有限公司'
    elif bad == 'date_role': item['date_label'] = '申请日期'
    elif bad == 'effective': item['effective_on'] = '2026-09-09'
    elif bad == 'direction': item['new_name'] = 'ST乙'
    elif bad == 'kind': item['kind'] = 'warning_removed'
    elif bad == 'future': item['observed_at'] = '2026-11-06T09:00:00+00:00'
    elif bad == 'publication': item['observed_at'] = '2026-09-06T12:00:00+00:00'
    else: item['source_url'] = 'https://example.com/title-only'
    with pytest.raises(ValueError): m.sse_proofs(folder, NOW)


def test_reconstruction_source_count_does_not_promote_independent_ST_coverage(tmp_path, monkeypatch):
    import market_risk
    fake = {'availability': 'reconstructed', 'through': None, 'metrics': {'all': {'member_day_observations': 100}}, 'source_venues': ['SSE','SZSE'],
            'verified_daily_membership_venues': ['SZSE'], 'historical_membership_verified': False}
    monkeypatch.setattr(market_risk, 'st_reconstruction_status', lambda *args, **kwargs: deepcopy(fake))
    status = lambda: market_risk.build_market_risk_status(snapshot_dir=tmp_path, database=tmp_path/'missing.db', manifest_path=tmp_path/'missing.json', now=NOW)
    assert status()['market_coverage']['st_reconstruction_source_venues_at_target'] == 0
    fake['through'] = '2026-11-04'
    monkeypatch.setattr(market_risk, '_public_indices', lambda *args, **kwargs: ({'availability':'observed','through':'2026-11-04','content_digest':'synthetic'},
        [{'code':'000985.CSI','through':'2026-11-04','historical_only':False,'observation_count':38}]))
    data = status()
    assert data['market_coverage']['st_reconstruction_source_venues_at_target'] == 2
    assert data['market_coverage']['st_reference_venues_at_target'] == 0 and data['market_coverage']['st_style_at_target'] is False
    assert data['parameters']['risk_weights'] is None and data['node_market_comparison']['status'] == 'not_evaluated'
    update = next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path, now=NOW) if r['source_id']=='combined_ST_reconstruction')
    assert update['coverage_basis'] == 'ST_reconstruction' and update['observed_source_groups'] == 2
    assert update['verified_membership_venues'] == 1 and update['series_at_target'] is None
    fake['availability'] = 'invalid'
    assert status()['market_coverage']['st_reconstruction_source_venues_at_target'] == 0
