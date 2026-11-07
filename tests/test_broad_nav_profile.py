"""The twelve-fund reader must preserve legacy scope and exact issuer evidence."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from etf_issuer_nav import BROAD_NAV_DEFINITIONS, BROAD_NAV_VERSION, NAV_DEFINITIONS, NAV_VERSION, load_issuer_navs
from etf_nav_refresh import IssuerNAVClient
from tests.etf_nav_fixtures import refresh_issuer_navs
from tests.test_etf_nav_sources import Complete, save

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
EXTRAS = tuple(code for code in BROAD_NAV_DEFINITIONS if code not in NAV_DEFINITIONS)


@pytest.fixture
def broad_snapshot(tmp_path):
    report = refresh_issuer_navs(Complete(), through='2026-11-04', output=tmp_path, now=NOW, version=BROAD_NAV_VERSION)
    assert report['status'] == 'complete'
    return tmp_path, json.loads((tmp_path/'current.json').read_text())


def test_twelve_profile_checks_732_values_and_52_primary_responses_without_expanding_cash_gates(broad_snapshot):
    folder, raw = broad_snapshot
    before = (folder/'current.json').read_bytes()
    meta, rows = load_issuer_navs(folder, NOW)
    assert raw['contract_version'] == BROAD_NAV_VERSION and len(rows) == 12
    assert IssuerNAVClient(folder, version=BROAD_NAV_VERSION).definitions == BROAD_NAV_DEFINITIONS
    audit = meta['raw_reconciliation']
    assert audit['nav_observations'] == 732 and audit['source_response_count'] == 52
    assert all(len(f['records']) == 61 and all(p['source_value'] == '2' for p in f['records']) for f in audit['funds'])
    assert all(audit[k] is False for k in ('historical_PIT', 'corporate_actions_checked', 'whole_fund_daily_scope_verified', 'share_precision_verified', 'final_revision_verified'))
    assert audit['estimated_net_subscription_yuan'] is None
    efunds = next(f for f in audit['funds'] if f['code'] == '588080.SH')
    assert 'asset_disclosure' not in efunds  # the 510310-specific asset review cannot migrate to STAR50
    assert (folder/'current.json').read_bytes() == before


@pytest.mark.parametrize('code', EXTRAS)
@pytest.mark.parametrize('bad', ['projection', 'raw_bytes', 'query', 'source_date'])
def test_each_added_fund_has_independent_raw_identity_and_date_binding(broad_snapshot, code, bad):
    folder, raw = broad_snapshot
    ref = next(r for r in raw['responses'] if r['code'] == code)
    if bad == 'projection':
        raw['etf_navs'][code][0]['unit_nav'] = 3
    elif bad == 'raw_bytes':
        (folder/'responses'/(ref['response_sha256']+'.raw')).write_bytes(b'changed')
    elif bad == 'query':
        ref['url'] = ref['url'].replace('https://', 'http://')
    else:
        for r in raw['responses']:
            if r['code'] == code:
                r['observed_at'] = '2026-08-01T00:00:00+00:00'
    save(folder, raw)
    assert load_issuer_navs(folder, NOW) == ({'availability': 'invalid'}, {})


@pytest.mark.parametrize('bad', ['legacy_version', 'unknown_version', 'missing', 'foreign', 'definition', 'duplicate'])
def test_profile_cannot_hide_missing_series_or_borrow_another_funds_evidence(broad_snapshot, bad):
    folder, raw = broad_snapshot
    if bad == 'legacy_version': raw['contract_version'] = NAV_VERSION
    elif bad == 'unknown_version': raw['contract_version'] = 'unregistered'
    elif bad == 'missing': raw['etf_navs'].pop('588080.SH')
    elif bad == 'foreign': raw['etf_navs']['000000.SH'] = raw['etf_navs'].pop('588080.SH')
    elif bad == 'definition': raw['definitions']['588080.SH'] = deepcopy(raw['definitions']['510310.SH'])
    else: raw['responses'].append(deepcopy(next(r for r in raw['responses'] if r['code'] == '588080.SH')))
    save(folder, raw)
    assert load_issuer_navs(folder, NOW) == ({'availability': 'invalid'}, {})


def test_legacy_eight_remains_supported_and_upgrade_preserves_every_old_point(tmp_path):
    refresh_issuer_navs(Complete(), through='2026-11-04', output=tmp_path, now=NOW)
    old_meta, old = load_issuer_navs(tmp_path, NOW)
    assert len(old) == 8 and old_meta['raw_reconciliation']['source_response_count'] == 34
    report = refresh_issuer_navs(Complete(), through='2026-11-04', output=tmp_path, now=NOW, version=BROAD_NAV_VERSION, repair=True)
    assert report['status'] == 'complete' and report['reused_series'] == 8
    assert {code: load_issuer_navs(tmp_path, NOW)[1][code] for code in old} == old


def test_downgrade_or_failure_of_new_fund_preserves_current_twelve(broad_snapshot):
    folder, _ = broad_snapshot
    before = (folder/'current.json').read_bytes()
    report = refresh_issuer_navs(Complete(), through='2026-11-04', output=folder, now=NOW)
    assert report['status'] == 'failed' and report['reason'] == 'would_regress_existing_scope'
    assert (folder/'current.json').read_bytes() == before
    class Missing(Complete):
        def get_navs(self, code, calendar):
            if code == '588080.SH': raise TimeoutError()
            return super().get_navs(code, calendar)
    report = refresh_issuer_navs(Missing(), through='2026-11-04', output=folder, now=NOW, version=BROAD_NAV_VERSION)
    assert report['status'] == 'failed' and report['complete_series'] == 11 and report['current_snapshot_preserved']
    assert (folder/'current.json').read_bytes() == before
