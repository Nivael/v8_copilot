from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
import exchange_risk_membership as legacy
import market_close_membership as m
import market_reading_updates as u
import test_exchange_risk_membership as old
from test_exchange_risk_membership import archive

NOW = datetime(2026, 11, 6, 16, 30, tzinfo=timezone.utc)  # Saturday in Shanghai
DAY = '2026-11-06'


def candidate(archive, monkeypatch):
    directory, payload, Fake = archive
    monkeypatch.setattr(old, 'NOW', NOW)
    for key, tables in payload.items():
        if key.startswith('szse_') and isinstance(tables, list):
            for table in tables:
                table['metadata']['subname'] = DAY + ' '
    collector = Fake()
    for key, (url, _) in legacy.PROOFS.items():
        collector.fetch(key, url, {})
    for key, group in legacy.GROUPS.items():
        if group['venue'] == 'SSE':
            collector.fetch(key, legacy.SSE_API, legacy.parameters(key))
        else:
            collector.fetch(key + ':1', legacy.SZSE_API, legacy.parameters(key))
            if key == 'szse_risk':
                collector.fetch(key + ':2', legacy.SZSE_API, legacy.parameters(key, 2))
    raw = {'version': 'exchange_risk_observation_candidate_v2', 'started_at': NOW.isoformat(),
           'completed_at': NOW.isoformat(), 'responses': collector.responses}
    raw['content_digest'] = digest(raw)
    atomic_write_json(directory / 'candidate.json', raw)
    return directory


def admitted(archive, monkeypatch):
    directory = candidate(archive, monkeypatch)
    return m.materialize_candidate(directory, now=NOW)


def closes(risk):
    return {row['ts_code']: {'security_name': row['name'], 'trade_date': DAY,
                             'is_trading': True, 'last': 9, 'prev_close': 10}
            for row in risk['rows'] if row['share_class'] == 'A'}


def test_actual_observation_and_declared_source_dates_are_independent(archive, monkeypatch):
    risk = admitted(archive, monkeypatch)
    before = (archive[0] / 'current.json').read_bytes()
    assert risk['observed_on'] == '2026-11-07'
    assert {g['source_as_of'] for g in risk['groups'] if g['venue'] == 'SZSE'} == {DAY}
    assert {g['source_as_of'] for g in risk['groups'] if g['venue'] == 'SSE'} == {None}
    assert (risk['risk_warning_a_shares'], risk['delisting_a_shares'], risk['excluded_b_shares']) == (5, 2, 2)
    assert m.load(archive[0], now=NOW) == risk
    assert (archive[0] / 'current.json').read_bytes() == before
    confirmation = m.confirm_close(risk, closes(risk), DAY, now=NOW)
    assert confirmation['through'] == DAY and confirmation['observed_on'] == '2026-11-07'
    assert confirmation['member_count'] == 5
    assert confirmation['historical_first_observation'] is confirmation['historical_PIT'] is False
    assert DAY in confirmation['note'] and '2026-11-07' in confirmation['note']


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'extra', 'url', 'params', 'redirect', 'time', 'bytes', 'definition'])
def test_admission_replays_exact_original_requests_and_definitions(archive, monkeypatch, bad):
    directory = candidate(archive, monkeypatch)
    raw = json.loads((directory / 'candidate.json').read_text())
    ref = raw['responses'][-1]
    if bad == 'missing': raw['responses'].pop()
    elif bad == 'duplicate': raw['responses'].append(deepcopy(ref))
    elif bad == 'extra': raw['responses'].append({**ref, 'key': 'unselected'})
    elif bad == 'url': ref['url'] = 'https://example.com/'
    elif bad == 'params': ref['params']['txtQueryDate'] = DAY
    elif bad == 'redirect': ref['final_url'] = 'https://example.com/'
    elif bad == 'time': ref['observed_at'] = (NOW + timedelta(seconds=1)).isoformat()
    elif bad == 'bytes': (directory / 'responses' / (ref['response_sha256'] + '.raw')).write_bytes(b'changed')
    else:
        ref = raw['responses'][0]
        (directory / 'responses' / (ref['response_sha256'] + '.raw')).write_bytes(b'changed definition')
    raw['content_digest'] = digest({k: v for k, v in raw.items() if k != 'content_digest'})
    atomic_write_json(directory / 'candidate.json', raw)
    with pytest.raises((ValueError, KeyError)):
        m.materialize_candidate(directory, now=NOW)
    assert not (directory / 'current.json').exists()


@pytest.mark.parametrize('bad', ['rewritten_day', 'naive', 'future', 'processor', 'raw_digest'])
def test_reader_does_not_relabel_or_repair_observation_metadata(archive, monkeypatch, bad):
    admitted(archive, monkeypatch)
    path = archive[0] / 'current.json'; raw = json.loads(path.read_text())
    if bad == 'rewritten_day': raw['observed_on'] = DAY
    elif bad == 'naive': raw['started_at'] = '2026-11-07T00:30:00'
    elif bad == 'future': raw['checked_at'] = (NOW + timedelta(seconds=1)).isoformat()
    elif bad == 'processor': raw['processor_digest'] = '0' * 64
    raw['content_digest'] = digest({k: v for k, v in raw.items() if k != 'content_digest'})
    if bad == 'raw_digest': raw['content_digest'] = '0' * 64
    atomic_write_json(path, raw); before = path.read_bytes()
    with pytest.raises(ValueError): m.load(archive[0], now=NOW)
    assert path.read_bytes() == before


@pytest.mark.parametrize('change', ['stale', 'future', 'mixed', 'malformed'])
def test_szse_dates_must_be_explicit_consistent_and_support_the_target(archive, monkeypatch, change):
    directory = candidate(archive, monkeypatch)
    raw = json.loads((directory / 'candidate.json').read_text())
    for ref in raw['responses']:
        if not ref['key'].startswith('szse_') or ref['key'] == 'szse_definition': continue
        path = directory / 'responses' / (ref['response_sha256'] + '.raw')
        body = json.loads(path.read_text())
        for table in body:
            if change == 'mixed' and ref['key'] != 'szse_risk:2': continue
            table['metadata']['subname'] = {'stale': '2026-11-05', 'future': '2026-11-08',
                                           'mixed': '2026-11-05', 'malformed': 'latest'}[change]
        encoded = json.dumps(body, ensure_ascii=False).encode()
        from hashlib import sha256
        ref['response_sha256'] = sha256(encoded).hexdigest(); ref['bytes'] = len(encoded)
        (directory / 'responses' / (ref['response_sha256'] + '.raw')).write_bytes(encoded)
    raw['content_digest'] = digest({k: v for k, v in raw.items() if k != 'content_digest'})
    atomic_write_json(directory / 'candidate.json', raw)
    if change == 'stale':
        risk = m.materialize_candidate(directory, now=NOW)
        with pytest.raises(ValueError, match='source dates'): m.confirm_close(risk, closes(risk), DAY, now=NOW)
    else:
        with pytest.raises(ValueError): m.materialize_candidate(directory, now=NOW)


@pytest.mark.parametrize('bad', ['intervening_session', 'same_day', 'nontrading_target', 'naive_now',
                                'wrong_venue', 'missing_group', 'name', 'missing_member', 'extra_member', 'mixed_day', 'empty'])
def test_later_confirmation_requires_calendar_dates_and_exact_closing_classification(archive, monkeypatch, bad):
    risk = admitted(archive, monkeypatch); rows = closes(risk); through = DAY; now = NOW
    if bad == 'intervening_session': through = '2026-11-05'
    elif bad == 'same_day': risk['observed_on'] = DAY
    elif bad == 'nontrading_target': through = '2026-11-07'
    elif bad == 'naive_now': now = NOW.replace(tzinfo=None)
    elif bad == 'wrong_venue': risk['groups'][0]['venue'] = 'SZSE'
    elif bad == 'missing_group': risk['groups'].pop()
    elif bad == 'name': rows['600001.SH']['security_name'] = 'ST另一家'
    elif bad == 'missing_member': rows.pop('600001.SH')
    elif bad == 'extra_member': rows['600003.SH'] = {**rows['600001.SH'], 'security_name': 'ST新增'}
    elif bad == 'mixed_day': rows['600001.SH']['trade_date'] = '2026-11-05'
    else: rows = {}
    with pytest.raises(ValueError): m.confirm_close(risk, rows, through, now=now)


def test_explicit_extension_retains_coverage_and_historical_limitations(archive, monkeypatch):
    from test_market_reading_updates import inputs
    base, _, _ = inputs(); base['through'] = '2026-11-05'
    for point, day in zip(base['points'], ['2026-11-04', '2026-11-05']): point['date'] = day
    risk = admitted(archive, monkeypatch); rows = closes(risk); calendar = ['2026-11-04', '2026-11-05', DAY]
    confirmation = m.confirm_close(risk, rows, DAY, now=NOW)
    with pytest.raises(ValueError, match='same-day'):
        u.extend_st(base, rows, risk, DAY, calendar)
    updated = u.extend_st(base, rows, risk, DAY, calendar, membership_confirmation=confirmation, now=NOW)
    assert updated['version'] == 'reading_ST_daily_extension_v2'
    assert updated['daily_close_extension']['membership_confirmation'] == confirmation
    assert updated['points'][-1]['all']['member_count'] == 5
    assert updated['historical_PIT'] is updated['historical_membership_verified'] is False
    assert base['through'] == '2026-11-05'
    changed = {**confirmation, 'observed_on': DAY}
    with pytest.raises(ValueError, match='confirmation changed'):
        u.extend_st(base, rows, risk, DAY, calendar, membership_confirmation=changed, now=NOW)
    rows['600001.SH'].update(is_trading=False, last=None, prev_close=None)
    with pytest.raises(ValueError, match='coverage'):
        u.extend_st(base, rows, risk, DAY, calendar, membership_confirmation=confirmation, now=NOW)


def test_v1_archive_is_read_without_date_or_projection_migration(archive):
    old.publish(archive); path = archive[0] / 'current.json'; before = path.read_bytes()
    assert m.load(archive[0], now=old.NOW) == legacy.list_status(archive[0], now=old.NOW)
    assert path.read_bytes() == before


def test_v1_update_cannot_adopt_a_new_later_observation_rule(tmp_path, monkeypatch):
    data = {'requested_through': '2026-11-05', 'snapshot_digest': 'b' * 64}
    source = 'a' * 64
    monkeypatch.setattr(u, 'source_files', lambda *_: {'mock': 'bytes'})
    monkeypatch.setattr(u, 'digest', lambda *_: source)
    raw = {'version': u.LEGACY_VERSION, 'base_binding': source, 'checked_at': NOW.isoformat(), 'through': DAY,
           'steps': [{'through': DAY, 'source_digest': source, 'membership_rule': m.RULE}]}
    with pytest.raises(ValueError, match='legacy updates cannot adopt'):
        u.replay(data, [], raw, output=tmp_path, now=NOW)
