from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from canonical_json import digest
from etf_szse_history import HTTP_API_URL, SZSE_CODES, archive_response, history_url
from etf_szse_refresh import SZSEHistoryClient
from etf_source_fixtures import refresh_szse_etfs
from etf_szse_recheck import materialize_recheck, recheck_status, refresh_recheck
from market_risk import build_market_risk_status
from test_etf_szse_refresh import CALENDAR, Client, block, rows

START = datetime(2026, 11, 5, 1, 35, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 5, 2, tzinfo=timezone.utc)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def resign(raw):
    raw['content_digest'] = digest({key: value for key, value in raw.items() if key != 'content_digest'})


@pytest.fixture
def setup(tmp_path):
    baseline, output, responses = tmp_path/'public_etf_szse', tmp_path/'szse_revision_recheck', tmp_path/'captured'
    refresh_szse_etfs(Client(), through='2026-11-04', output=baseline,
                      now=datetime(2026, 11, 4, 22, tzinfo=timezone.utc))
    source = json.loads((baseline/'current.json').read_text()); refs = []
    for code in SZSE_CODES:
        for nav in (False, True):
            data = rows(code, nav=nav)[-11:-1] if nav else rows(code)
            payload = block(data, nav=nav)
            if nav: payload[0]['metadata'].update(pagesize=-1, pageno=0, pagecount=0, recordcount=0)
            raw = json.dumps(payload).encode(); sha = hashlib.sha256(raw).hexdigest()
            responses.mkdir(exist_ok=True); (responses/f'{sha}.json').write_bytes(raw)
            refs.append({'code': code, 'kind': 'NAV' if nav else 'shares', 'page': 1,
                         'url': history_url(HTTP_API_URL, code, CALENDAR, nav=nav), 'response_sha256': sha,
                         'observed_at': START.isoformat()})
    args = dict(baseline_dir=baseline, baseline_digest=source['content_digest'], output=output, response_dir=responses,
                responses=refs, started_at=START.isoformat(), completed_at=START.isoformat(), now=NOW)
    return args


def status(args, issuer=None):
    return recheck_status(args['output'], args['baseline_dir'], NOW, issuer)


def materialize(args):
    return materialize_recheck(**args)


def test_actual_http_raw_replay_preserves_fetch_times_and_original_without_final_promotion(setup):
    original = (setup['baseline_dir']/'current.json').read_bytes()
    report = materialize(setup); data = status(setup)
    assert report['status'] == data['availability'] == 'observed'
    assert data['share_observations'] == 63 and data['share_changes'] == 0
    assert data['nav_observations'] == 30 and data['sessions'] == 21
    assert data['first_observed_at'] == data['last_observed_at'] == START.isoformat()
    assert data['transport'] == 'HTTP' and data['api_url'] == HTTP_API_URL
    assert data['final_revision_verified'] is False and data['estimated_net_subscription_yuan'] is None
    assert data['corporate_actions_checked'] is False
    assert all(fund['nav_through'] == '2026-11-03' for fund in data['funds'])
    assert all(fund['nav_comparison']['missing_previous_dates'] == CALENDAR[:-11] for fund in data['funds'])
    assert all(fund['issuer_nav_comparison']['overlap_observations'] == 0 for fund in data['funds'])
    assert (setup['baseline_dir']/'current.json').read_bytes() == original


def replace_response(args, index, mutate):
    ref = args['responses'][index]
    path = args['response_dir']/f"{ref['response_sha256']}.json"
    payload = json.loads(path.read_bytes()); mutate(payload)
    raw = json.dumps(payload).encode(); sha = hashlib.sha256(raw).hexdigest()
    (args['response_dir']/f'{sha}.json').write_bytes(raw); ref['response_sha256'] = sha


def test_changed_share_and_nav_records_are_differences_not_flows_or_overwritten_prices(setup):
    replace_response(setup, 0, lambda value: value[0]['data'][-1].update(current_size='1,234.57'))
    replace_response(setup, 1, lambda value: value[0]['data'][-1].update(nav_per_share='4.1235'))
    materialize(setup)
    issuer = {code: [{'nav_date': day, 'unit_nav': 4.1234} for day in CALENDAR] for code in SZSE_CODES}
    data = status(setup, issuer); fund = data['funds'][0]
    assert data['share_changes'] == 1
    assert fund['share_comparison']['changes'] == [{'date': '2026-11-04', 'before': '1234.56', 'after': '1234.57', 'difference': '0.01'}]
    assert fund['nav_comparison']['changes'][0]['difference'] == '0.0001'
    assert fund['issuer_nav_comparison']['overlap_observations'] == 10
    assert fund['issuer_nav_comparison']['changed_observations'] == 1
    assert data['estimated_net_subscription_yuan'] is None and data['final_revision_verified'] is False
    assert json.loads((setup['baseline_dir']/'current.json').read_text())['etf_shares']['159919.SZ'][-1]['fd_share'] == 1234.56


@pytest.mark.parametrize('bad', ['missing_kind', 'missing_product', 'duplicate_page', 'wrong_code', 'wrong_url', 'wrong_range',
                                 'wrong_catalog', 'wrong_page', 'bool_page', 'redirect_endpoint', 'mixed_transport',
                                 'bad_hash', 'future_observation', 'before_start', 'naive_time'])
def test_reference_identity_scope_query_pagination_and_times_cannot_be_rehashed_into_validity(setup, bad):
    refs = setup['responses']
    if bad == 'missing_kind': refs.pop()
    elif bad == 'missing_product': refs[:] = [ref for ref in refs if ref['code'] != SZSE_CODES[-1]]
    elif bad == 'duplicate_page': refs.append(deepcopy(refs[0]))
    elif bad == 'wrong_code': refs[0]['code'] = '510300.SH'
    elif bad == 'wrong_url': refs[0]['url'] += '&txtDm=159922'
    elif bad == 'wrong_range': refs[0]['url'] = refs[0]['url'].replace(CALENDAR[0], CALENDAR[1])
    elif bad == 'wrong_catalog': refs[0]['url'] = refs[0]['url'].replace('fund_jjgm', 'fund_jjjz')
    elif bad == 'wrong_page': refs[0]['page'] = 2
    elif bad == 'bool_page': refs[0]['page'] = True
    elif bad == 'redirect_endpoint': refs[0]['url'] = refs[0]['url'].replace('fund.szse.cn', 'example.com')
    elif bad == 'mixed_transport': refs[0]['url'] = refs[0]['url'].replace('http:', 'https:')
    elif bad == 'bad_hash': refs[0]['response_sha256'] = '../bad'
    elif bad == 'future_observation': refs[0]['observed_at'] = NOW.isoformat()
    elif bad == 'before_start': refs[0]['observed_at'] = '2026-11-05T01:34:00+00:00'
    else: refs[0]['observed_at'] = '2026-11-05T01:35:00'
    with pytest.raises((ValueError, OSError)): materialize(setup)
    assert not (setup['output']/'current.json').exists()


@pytest.mark.parametrize('bad', ['missing_day', 'wrong_unit', 'duplicate_date', 'wrong_code', 'count', 'bool_count', 'fractional_page', 'zero'])
def test_complete_raw_share_calendar_and_units_required(setup, bad):
    def mutate(value):
        if bad == 'missing_day': value[0]['data'].pop(); value[0]['metadata']['recordcount'] -= 1
        elif bad == 'wrong_unit': value[0]['metadata']['cols']['current_size'] = '基金规模(亿元)'
        elif bad == 'duplicate_date': value[0]['data'][1] = deepcopy(value[0]['data'][0])
        elif bad == 'wrong_code': value[0]['data'][0]['fund_code'] = '159922'
        elif bad == 'count': value[0]['metadata']['recordcount'] += 1
        elif bad == 'bool_count': value[0]['metadata']['recordcount'] = True
        elif bad == 'fractional_page': value[0]['metadata']['pageno'] = 1.5
        else: value[0]['data'][0]['current_size'] = 0
    replace_response(setup, 0, mutate)
    with pytest.raises(ValueError): materialize(setup)


def test_reader_reparses_raw_bytes_and_does_not_trust_rehashed_summary(setup):
    materialize(setup)
    path = setup['output']/'responses'/f"{setup['responses'][0]['response_sha256']}.json"
    path.write_bytes(b'[]')
    assert status(setup)['availability'] == 'invalid'
    assert status(setup)['share_changes'] is None


@pytest.mark.parametrize('field,value', [('processor_digest', '0'*64), ('share_revision_status', 'final'),
                                       ('availability_basis', 'historical_PIT'), ('completed_at', '2026-11-06T02:00:00+00:00')])
def test_recomputed_snapshot_digest_cannot_promote_version_or_availability(setup, field, value):
    materialize(setup); path = setup['output']/'current.json'
    raw = json.loads(path.read_text()); raw[field] = value; resign(raw); write_json(path, raw)
    assert status(setup)['availability'] == 'invalid'


def test_baseline_changed_invalidates_old_recheck_and_prevents_replay_against_new_snapshot(setup):
    materialize(setup); path = setup['baseline_dir']/'current.json'
    raw = json.loads(path.read_text()); raw['etf_shares'][SZSE_CODES[0]][0]['fd_share'] += 1; resign(raw); write_json(path, raw)
    assert status(setup)['availability'] == 'baseline_changed'
    with pytest.raises(ValueError, match='baseline changed'): materialize(setup)


@pytest.mark.parametrize('relation', ['same', 'ancestor', 'descendant'])
def test_recheck_cannot_write_inside_or_over_original_snapshot(setup, relation):
    baseline = setup['baseline_dir']; original = (baseline/'current.json').read_bytes()
    setup['output'] = {'same': baseline, 'ancestor': baseline.parent, 'descendant': baseline/'nested'}[relation]
    with pytest.raises(ValueError, match='separate'): materialize(setup)
    assert (baseline/'current.json').read_bytes() == original


def test_partial_collection_failure_preserves_last_complete_recheck_and_baseline(setup):
    materialize(setup); previous = (setup['output']/'current.json').read_bytes()
    original = (setup['baseline_dir']/'current.json').read_bytes()
    class Failed:
        response_dir = setup['response_dir']
        def get_history(self, code, calendar, *, nav=False):
            if nav: raise TimeoutError('upstream detail')
            return [], [setup['responses'][0]]
    report = refresh_recheck(Failed(), baseline_dir=setup['baseline_dir'], output=setup['output'], now=NOW)
    assert report == {'status': 'failed', 'reason': 'TimeoutError', 'current_snapshot_preserved': True}
    assert (setup['output']/'current.json').read_bytes() == previous
    assert (setup['baseline_dir']/'current.json').read_bytes() == original


def test_api_keeps_revision_and_cash_gates_and_core_dates_after_successful_recheck(setup):
    materialize(setup)
    data = build_market_risk_status(snapshot_dir=setup['output'].parent, database=Path('/missing.db'),
                                    manifest_path=Path('/missing.json'), now=NOW)
    assert data['szse_revision_recheck']['availability'] == 'observed'
    assert all(etf['share_revision_unverified'] for etf in data['etfs'])
    assert data['etf_aggregate']['5']['revision_unconfirmed_etfs'] == 3
    assert all(row['estimated_net_subscription_yuan'] is None for row in data['etf_aggregate'].values())
    assert data['current_risk_assessment'] == 'not_calibrated'
    assert data['node_market_comparison']['status'] == 'not_evaluated'


def test_transport_is_allowlisted_and_redirected_responses_are_not_archived(tmp_path, monkeypatch):
    with pytest.raises(ValueError): SZSEHistoryClient(tmp_path, api_url='https://example.com')
    class Redirect:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def geturl(self): return 'http://example.com/fake'
        def read(self, *_): pytest.fail('redirect content must not be read')
    monkeypatch.setattr('etf_szse_refresh.urlopen', lambda *_args, **_kwargs: Redirect())
    with pytest.raises(ValueError, match='redirect'): SZSEHistoryClient(tmp_path).get_history(SZSE_CODES[0], CALENDAR)
    assert not list(tmp_path.iterdir())


def test_explicit_http_collector_records_actual_api_without_labeling_it_https(tmp_path):
    client = Client(); client.api_url = HTTP_API_URL
    refresh_szse_etfs(client, through='2026-11-04', output=tmp_path, now=NOW)
    raw = json.loads((tmp_path/'current.json').read_text())
    assert raw['api_url'] == HTTP_API_URL
    assert raw['share_revision_status'] == 'final_revision_unverified'


def test_failed_response_replacement_preserves_old_bytes_and_cleans_temporary_file(tmp_path, monkeypatch):
    path = tmp_path/'existing.json'; path.write_bytes(b'original')
    def fail(*_): raise OSError('replacement failed')
    monkeypatch.setattr('etf_szse_history.os.replace', fail)
    with pytest.raises(OSError): archive_response(path, b'new complete response')
    assert path.read_bytes() == b'original'
    assert sorted(item.name for item in tmp_path.iterdir()) == ['existing.json']
