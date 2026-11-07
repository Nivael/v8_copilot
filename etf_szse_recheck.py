"""Archive and reparse a later SZSE observation without certifying final revisions."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from etf_szse_history import API_URL, HTTP_API_URL, SOURCE_URL, SZSE_CODES, archive_response, history_url, number, parse_history
from market_calendar import CALENDAR_VERSION, sessions_2026
from settings import DATA_ROOT

VERSION = 'szse_etf_revision_recheck_v1'
DEFAULT_ROOT = DATA_ROOT / 'local_data/v8_copilot/market_risk'
NOTE = '目标日后重读只证明本次观察与所绑定快照的差异；未取得足以确认最终修订版的已核验证据。净值仅比较实际返回日期，不补齐为完整窗，净申赎金额继续未发布。'


def processor_digest():
    root = Path(__file__).parent
    return digest({name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                   (Path(__file__).name, 'etf_szse_history.py', 'etf_szse_refresh.py', 'market_calendar.py', 'canonical_json.py')})


PROCESSOR_DIGEST = processor_digest()


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None: raise ValueError('timezone required')
    return result


def baseline_snapshot(directory: Path, now: datetime):
    raw = json.loads((directory/'current.json').read_text())
    unsigned = {key: value for key, value in raw.items() if key != 'content_digest'}
    calendar = raw['calendar']; through = date.fromisoformat(raw['requested_through'])
    if (raw['content_digest'] != digest(unsigned) or raw['contract_version'] != 'szse_etf_history_raw_v1'
        or raw['provider'] != 'szse_public' or raw['share_unit'] != 'ten_thousand_shares'
        or raw['nav_unit'] != 'CNY_per_share' or raw['source_url'] != SOURCE_URL or raw['api_url'] not in (API_URL, HTTP_API_URL)
        or raw['calendar_version'] != CALENDAR_VERSION or raw['share_revision_status'] != 'final_revision_unverified'
        or not 21 <= len(calendar) <= 61 or calendar[-1] != through.isoformat()
        or calendar != sessions_2026(date.fromisoformat(calendar[0]), through)
        or through >= now.astimezone(ZoneInfo('Asia/Shanghai')).date()
        or not through <= timestamp(raw['fetched_at']).astimezone(ZoneInfo('Asia/Shanghai')).date() <= now.astimezone(ZoneInfo('Asia/Shanghai')).date()
        or timestamp(raw['fetched_at']) > now): raise ValueError('invalid bound baseline')
    for key, day_key, value_key in (('etf_shares', 'trade_date', 'fd_share'), ('etf_navs', 'nav_date', 'unit_nav')):
        if set(raw[key]) != set(SZSE_CODES): raise ValueError('wrong baseline products')
        for code, rows in raw[key].items():
            days = [row[day_key] for row in rows]
            if (not rows or days != sorted(set(days)) or any(day not in calendar for day in days)
                or key == 'etf_shares' and days != calendar
                or any(row['ts_code'] != code or (number(row[value_key]) or 0) <= 0 for row in rows)):
                raise ValueError('incomplete or invalid bound baseline')
    return raw


def differences(old, new, day_key, value_key):
    before = {row[day_key]: Decimal(str(row[value_key])) for row in old}
    after = {row[day_key]: Decimal(str(row[value_key])) for row in new}
    common = sorted(before.keys() & after.keys())
    changed = [{'date': day, 'before': str(before[day]), 'after': str(after[day]),
                'difference': str(after[day]-before[day])} for day in common if before[day] != after[day]]
    return {'overlap_observations': len(common), 'changed_observations': len(changed), 'changes': changed,
            'new_dates': sorted(after.keys()-before.keys()), 'missing_previous_dates': sorted(before.keys()-after.keys())}


def validate_recheck(raw, response_dir: Path, baseline, now: datetime, issuer_navs=None):
    """Reconstruct counts/differences from byte-bound raw pages on every read."""
    unsigned = {key: value for key, value in raw.items() if key != 'content_digest'}
    started, completed = timestamp(raw['started_at']), timestamp(raw['completed_at'])
    if (raw['content_digest'] != digest(unsigned) or raw['contract_version'] != VERSION
        or raw['processor_digest'] != PROCESSOR_DIGEST or raw['baseline_digest'] != baseline['content_digest']
        or raw['baseline_fetched_at'] != baseline['fetched_at'] or raw['calendar'] != baseline['calendar']
        or raw['through'] != baseline['requested_through'] or raw['calendar_version'] != CALENDAR_VERSION
        or raw['share_revision_status'] != 'final_revision_unverified'
        or raw['availability_basis'] != 'later_observed_not_historical_PIT'
        or not timestamp(baseline['fetched_at']) <= started <= completed <= now
        or started.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() <= raw['through']):
        raise ValueError('recheck does not bind to current baseline, processor or time')
    refs = raw['responses']
    if not 6 <= len(refs) <= 60: raise ValueError('incomplete or excessive recheck responses')
    endpoints = {ref['url'].split('?', 1)[0] for ref in refs}
    if len(endpoints) != 1 or not endpoints <= {API_URL, HTTP_API_URL}: raise ValueError('unexpected mixed transport')
    api_url = next(iter(endpoints)); groups = {}
    for ref in refs:
        code, kind, page = ref['code'], ref['kind'], ref['page']
        if (code not in SZSE_CODES or kind not in ('shares', 'NAV') or type(page) is not int or not 1 <= page <= 10
            or ref['url'] != history_url(api_url, code, raw['calendar'], nav=kind == 'NAV', page=page)
            or not started <= timestamp(ref['observed_at']) <= completed
            or not re.fullmatch(r'[0-9a-f]{64}', ref['response_sha256'])): raise ValueError('invalid response identity/query/time')
        data = (response_dir/f"{ref['response_sha256']}.json").read_bytes()
        if len(data) > 4_000_000 or hashlib.sha256(data).hexdigest() != ref['response_sha256']:
            raise ValueError('recheck raw bytes changed')
        pages = groups.setdefault((code, kind), {})
        if page in pages: raise ValueError('duplicate response page')
        pages[page] = json.loads(data)
    if set(groups) != {(code, kind) for code in SZSE_CODES for kind in ('shares', 'NAV')}:
        raise ValueError('missing product or history kind')
    funds = []
    for code in SZSE_CODES:
        normalized = {}
        for kind in ('shares', 'NAV'):
            pages = groups[(code, kind)]
            if sorted(pages) != list(range(1, len(pages)+1)): raise ValueError('incomplete page sequence')
            rows = parse_history([pages[page] for page in sorted(pages)], code, raw['calendar'], nav=kind == 'NAV')
            if not rows or kind == 'shares' and [row['trade_date'] for row in rows] != raw['calendar']:
                raise ValueError('share window incomplete or NAV absent')
            normalized[kind] = rows
        shares = differences(baseline['etf_shares'][code], normalized['shares'], 'trade_date', 'fd_share')
        nav = differences(baseline['etf_navs'][code], normalized['NAV'], 'nav_date', 'unit_nav')
        issuer = differences((issuer_navs or {}).get(code, []), normalized['NAV'], 'nav_date', 'unit_nav')
        funds.append({'code': code, 'share_observations': len(normalized['shares']), 'share_comparison': shares,
                      'latest_shares_ten_thousand': str(normalized['shares'][-1]['fd_share']),
                      'nav_observations': len(normalized['NAV']), 'nav_through': normalized['NAV'][-1]['nav_date'],
                      'nav_comparison': nav, 'issuer_nav_comparison': {'overlap_observations': issuer['overlap_observations'],
                           'changed_observations': issuer['changed_observations'], 'changes': issuer['changes']}})
    return {'version': VERSION, 'availability': 'observed', 'through': raw['through'], 'start': raw['calendar'][0],
            'sessions': len(raw['calendar']), 'started_at': raw['started_at'], 'completed_at': raw['completed_at'],
            'first_observed_at': min((ref['observed_at'] for ref in refs), key=timestamp),
            'last_observed_at': max((ref['observed_at'] for ref in refs), key=timestamp),
            'baseline_digest': raw['baseline_digest'], 'baseline_fetched_at': raw['baseline_fetched_at'],
            'content_digest': raw['content_digest'], 'processor_digest': PROCESSOR_DIGEST, 'api_url': api_url,
            'source_url': SOURCE_URL, 'transport': 'HTTP' if api_url == HTTP_API_URL else 'HTTPS',
            'share_observations': sum(fund['share_observations'] for fund in funds),
            'share_changes': sum(fund['share_comparison']['changed_observations'] for fund in funds),
            'nav_observations': sum(fund['nav_observations'] for fund in funds), 'responses': refs, 'funds': funds,
            'share_revision_status': 'final_revision_unverified', 'final_revision_verified': False,
            'corporate_actions_checked': False, 'estimated_net_subscription_yuan': None, 'note': NOTE}


def recheck_status(directory: Path, baseline_dir: Path, now: datetime, issuer_navs=None):
    base = {'version': VERSION, 'availability': 'missing', 'funds': [], 'share_observations': 0, 'nav_observations': 0,
            'share_changes': None, 'final_revision_verified': False, 'share_revision_status': 'final_revision_unverified',
            'corporate_actions_checked': False, 'estimated_net_subscription_yuan': None, 'note': NOTE}
    if processor_digest() != PROCESSOR_DIGEST: return {**base, 'availability': 'reload_required'}
    try:
        raw = json.loads((directory/'current.json').read_text())
        baseline = baseline_snapshot(baseline_dir, now)
        if raw.get('baseline_digest') != baseline['content_digest']: return {**base, 'availability': 'baseline_changed'}
        return validate_recheck(raw, directory/'responses', baseline, now, issuer_navs)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError):
        return {**base, 'availability': 'invalid' if (directory/'current.json').exists() else 'missing'}


def separate_output(output: Path, baseline_dir: Path):
    output, baseline_dir = output.resolve(), baseline_dir.resolve()
    if output == baseline_dir or output in baseline_dir.parents or baseline_dir in output.parents:
        raise ValueError('recheck output must be separate from original snapshot')


def materialize_recheck(*, baseline_dir: Path, baseline_digest: str, output: Path, response_dir: Path, responses: list,
                        started_at: str, completed_at: str, now: datetime):
    """Support both live responses and explicit offline replay, preserving fetch times."""
    separate_output(output, baseline_dir)
    if processor_digest() != PROCESSOR_DIGEST: raise ValueError('reload processor before materialization')
    baseline = baseline_snapshot(baseline_dir, now)
    if baseline['content_digest'] != baseline_digest: raise ValueError('baseline changed since collection')
    raw = {'contract_version': VERSION, 'processor_digest': PROCESSOR_DIGEST,
           'baseline_digest': baseline['content_digest'], 'baseline_fetched_at': baseline['fetched_at'],
           'calendar': baseline['calendar'], 'through': baseline['requested_through'], 'calendar_version': CALENDAR_VERSION,
           'started_at': started_at, 'completed_at': completed_at, 'responses': responses,
           'share_revision_status': 'final_revision_unverified', 'availability_basis': 'later_observed_not_historical_PIT'}
    raw['content_digest'] = digest(raw)
    result = validate_recheck(raw, response_dir, baseline, now)
    # Copy only byte-checked responses. Publication follows full three-product validation.
    (output/'responses').mkdir(parents=True, exist_ok=True)
    for ref in responses:
        name = f"{ref['response_sha256']}.json"
        archive_response(output/'responses'/name, (response_dir/name).read_bytes())
    validate_recheck(raw, output/'responses', baseline, now)
    if baseline_snapshot(baseline_dir, now)['content_digest'] != baseline['content_digest']:
        raise ValueError('baseline changed during recheck')
    atomic_write_json(output/'snapshots'/f"{raw['content_digest']}.json", raw)
    atomic_write_json(output/'current.json', raw)
    return {'status': 'observed', 'content_digest': raw['content_digest'], 'baseline_digest': baseline['content_digest'],
            'share_observations': result['share_observations'], 'share_changes': result['share_changes'],
            'nav_observations': result['nav_observations'], 'final_revision_verified': False}


def refresh_recheck(client, *, baseline_dir: Path, output: Path, now: datetime | None = None):
    separate_output(output, baseline_dir)
    started = now or datetime.now(timezone.utc)
    try:
        baseline = baseline_snapshot(baseline_dir, started); refs = []
        for code in SZSE_CODES:
            for nav in (False, True):
                _, responses = client.get_history(code, baseline['calendar'], nav=nav)
                refs.extend(responses)
        completed = now or datetime.now(timezone.utc)
        report = materialize_recheck(baseline_dir=baseline_dir, baseline_digest=baseline['content_digest'], output=output, response_dir=client.response_dir,
                                    responses=refs, started_at=started.isoformat(), completed_at=completed.isoformat(), now=completed)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as exc:
        report = {'status': 'failed', 'reason': type(exc).__name__, 'current_snapshot_preserved': True}
    atomic_write_json(output/'last_attempt.json', report)
    return report


def main():
    from etf_szse_refresh import SZSEHistoryClient
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=DEFAULT_ROOT/'public_etf_szse')
    parser.add_argument('--output', type=Path, default=DEFAULT_ROOT/'szse_revision_recheck')
    parser.add_argument('--transport', choices=('https', 'http'), default='https')
    args = parser.parse_args()
    separate_output(args.output, args.baseline)
    client = SZSEHistoryClient(args.output/'responses', api_url=HTTP_API_URL if args.transport == 'http' else API_URL)
    report = refresh_recheck(client, baseline_dir=args.baseline, output=args.output)
    print(json.dumps(report, ensure_ascii=False))
    return 2 if report['status'] == 'failed' else 0


if __name__ == '__main__': raise SystemExit(main())
