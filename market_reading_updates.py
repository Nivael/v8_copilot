"""Verified daily reading updates, preserving the frozen historical source plans."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from broad_etf_reading import bound_packet, build_broad_etf_reading
from canonical_json import digest
from combined_st_reference import sample
from data_refresh import atomic_write_json
from exchange_risk_membership import list_status
from market_breadth import cross_section, st_name
from market_calendar import sessions_2026
from market_periods import recent_calendar_window
from market_public_refresh import parse_index_perf
from market_risk import MARKET_RISK_DIR, CSI_PERF_URL, _public_indices, _public_etfs, _szse_etfs
from trader_research_notes import capital_actions
from trader_swing_reading import closing_day

VERSION = 'market_reading_daily_updates_v1'
OUTPUT = MARKET_RISK_DIR / 'trader_observations/reading_updates'
SOURCE_FOLDERS = ('public_indices', 'public_etf', 'public_etf_szse', 'trader_observations/broad_indices', 'risk')


def processor_digest():
    names = ('market_reading_updates.py', 'market_public_refresh.py', 'market_risk.py', 'broad_etf_reading.py',
             'etf_daily_sources.py', 'etf_szse_history.py', 'trader_swing_reading.py', 'combined_st_reference.py',
             'exchange_risk_membership.py', 'market_breadth.py', 'market_calendar.py', 'market_periods.py')
    return digest({name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names})


def base_binding(data):
    return digest({'through': data['requested_through'], 'snapshot': data['snapshot_digest'],
                   'sources': {name: data.get(name, {}).get('content_digest') for name in
                               ('st_reconstruction', 'combined_breadth_history', 'sse_history_archive',
                                'breadth_history', 'public_etf_snapshot', 'szse_etf_snapshot')}})


def source_files(folder):
    result = {}
    for name in SOURCE_FOLDERS:
        directory = folder / name
        current = directory / 'current.json'
        if directory.is_symlink() or current.is_symlink() or (directory / 'responses').is_symlink():
            raise ValueError('source symlinks are not accepted')
        files = [current, *sorted((directory / 'responses').glob('*'))]
        for path in files:
            if path.is_symlink() or not path.is_file():
                raise ValueError('invalid source file')
            result[str(path.relative_to(folder))] = sha256(path.read_bytes()).hexdigest()
    return result


def next_session(previous, through):
    if sessions_2026(date.fromisoformat(previous), date.fromisoformat(through)) != [previous, through]:
        raise ValueError('each update must cover exactly the next trading session')


def extend_st(base, rows, risk, through, calendar):
    previous = base['through']
    next_session(previous, through)
    if base['availability'] != 'reconstructed' or base['points'][-1]['date'] != previous:
        raise ValueError('complete ST base required')
    if risk['availability'] != 'observed' or risk['observed_on'] != through:
        raise ValueError('same-day independently observed risk list required')
    members = {r['ts_code']: r['name'] for r in risk['rows'] if r['kind'] == 'risk_warning' and r['share_class'] == 'A'}
    flagged = {code for code, row in rows.items() if st_name(row['security_name'])}
    if not members or set(members) != flagged:
        raise ValueError('risk list and complete closing-name group differ')
    for code, name in members.items():
        if rows[code]['trade_date'] != through or re.sub(r'\s+', '', name) != re.sub(r'\s+', '', rows[code]['security_name']):
            raise ValueError('risk/close name or date mismatch')
    sse = {s for s in members if s.endswith('.SH')}
    szse = {s for s in members if s.endswith('.SZ')}
    sm, sv = sample(sse, rows)
    zm, zv = sample(szse, rows)
    values = sv + zv
    total = len(members)
    allm = {'member_count': total, 'observed_members': len(values), 'coverage_ratio': len(values) / total,
            'missing_symbols': sorted(sm['missing_symbols'] + zm['missing_symbols']),
            'daily_return_pct': float(sum(values) / len(values)) if values else None}
    point = {'date': through, 'all': allm, 'SSE': sm, 'SZSE': zm}
    for group in ('all', 'SSE', 'SZSE'):
        if point[group]['coverage_ratio'] < base['coverage_threshold'] or point[group]['daily_return_pct'] is None:
            raise ValueError('daily ST coverage below the unchanged base gate')
        point[group]['close'] = round(base['points'][-1][group]['close'] * (1 + point[group]['daily_return_pct'] / 100), 8)
    result = deepcopy(base)
    result['points'] = [p for p in result['points'] if p['date'] in calendar] + [point]
    if [p['date'] for p in result['points']] != calendar:
        raise ValueError('ST update has a missing common session')
    result['start'], result['through'] = calendar[0], through
    result['memberships'] = [p for p in result.get('memberships', []) if p['date'] in calendar] + [
        {'date': through, 'SSE': sorted(sse), 'SZSE': sorted(szse)}]
    result['sse_endpoint_members'], result['szse_endpoint_members'] = len(sse), len(szse)
    for group in ('all', 'SSE', 'SZSE'):
        points = [p[group] for p in result['points']]
        peak = Decimal('0'); drawdown = Decimal('0')
        for p in points:
            value = Decimal(str(p['close'])); peak = max(peak, value)
            drawdown = min(drawdown, (value / peak - 1) * 100)
        result['metrics'][group] = {'return_pct': (points[-1]['close'] / points[0]['close'] - 1) * 100,
                                    'max_drawdown_pct': float(drawdown),
                                    'minimum_coverage': min(p['coverage_ratio'] for p in points),
                                    'member_day_observations': sum(p['member_count'] for p in points),
                                    'observed_member_days': sum(p['observed_members'] for p in points)}
    # The original SSE historical-membership and PIT limitations remain unchanged.
    result['daily_close_extension'] = {'through': through, 'membership_digest': risk['content_digest'],
                                       'observed_members': len(values), 'member_count': total}
    result['version'] = 'reading_ST_daily_extension_v1'
    result['base_reference_digest'] = base.get('base_reference_digest', base.get('content_digest'))
    result['content_digest'] = digest({k: v for k, v in result.items() if k != 'content_digest'})
    return result


def extend_watch(bases, rows, previous, through):
    next_session(previous, through)
    result = deepcopy(bases)
    for basis in result:
        if basis.get('availability') != 'available':
            continue
        symbol = basis['symbol']; row = rows[symbol]
        if basis['as_of'] != previous or basis['prices'][-1]['date'] != previous or row['trade_date'] != through:
            raise ValueError('watch update does not follow its verified base')
        basis['prices'].append({'date': through, 'close': row['last'] if row['is_trading'] else None,
                                'previous_close': row['prev_close'] if row['is_trading'] else None,
                                'is_trading': row['is_trading']})
        basis.update(as_of=through, name=row['security_name'])
    return result


def project_step(data, bases, folder, through, *, root=MARKET_RISK_DIR, now=None):
    now = now or datetime.now(timezone.utc)
    if through >= now.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():
        raise ValueError('completed daily observations only')
    next_session(data['requested_through'], through)
    index_meta, indices = _public_indices(folder / 'public_indices', now)
    share_meta, sse_funds = _public_etfs(folder / 'public_etf', now)
    szse_meta, szse_funds = _szse_etfs(folder / 'public_etf_szse', now)
    if any(meta.get('availability') != 'observed' or meta.get('through') != through for meta in (index_meta, share_meta, szse_meta)):
        raise ValueError('matching verified index and ETF source dates required')
    raw = bound_packet(folder / 'public_indices/current.json'); calendar = raw['calendar']
    if len(raw['responses']) != len(indices) or {r['code'] for r in raw['responses']} != set(raw['indices']):
        raise ValueError('index originals incomplete')
    for ref in raw['responses']:
        url = CSI_PERF_URL + '?' + urlencode({'indexCode': ref['code'][:6], 'startDate': calendar[0].replace('-', ''),
                                             'endDate': through.replace('-', '')})
        original = (folder / 'public_indices/responses' / (ref['response_sha256'] + '.json')).read_bytes()
        observed = datetime.fromisoformat(ref['observed_at'])
        if ref['url'] != url or sha256(original).hexdigest() != ref['response_sha256'] or observed.tzinfo is None or observed > now:
            raise ValueError('index original identity or observation changed')
        if parse_index_perf(json.loads(original), ref['code'], calendar) != raw['indices'][ref['code']]:
            raise ValueError('index projection differs from the original')
    funds = sse_funds + szse_funds
    if len(funds) != 8 or any(f['through'] != through or f['share_observation_count'] != len(calendar) for f in funds):
        raise ValueError('complete declared ETF share windows required')
    period = recent_calendar_window(through)
    if period['availability'] != 'defined':
        raise ValueError('common recent calendar required')
    risk = list_status(folder / 'risk', now=now)
    closes = {}; close_digests = {}
    for venue in ('SSE', 'SZSE'):
        rows, key = closing_day(root, through, venue)
        if set(rows) & set(closes):
            raise ValueError('duplicate cross-venue security')
        closes.update(rows); close_digests[venue] = key
    st = extend_st(data['st_reconstruction'], closes, risk, through, period['calendar'])
    result = {**data, 'requested_through': through, 'indices': indices, 'etfs': funds, 'recent_window': period,
              'public_etf_snapshot': share_meta, 'szse_etf_snapshot': szse_meta, 'public_index_snapshot': index_meta,
              'st_reconstruction': st,
              'combined_breadth_history': {'version': 'reading_breadth_daily_extension_v1', 'availability': 'observed',
                  'start': period['start'], 'through': through,
                  'base_reference_digest': data['combined_breadth_history'].get('base_reference_digest', data['combined_breadth_history'].get('content_digest')),
                  'points': [p for p in data['combined_breadth_history']['points'] if p['date'] in period['calendar']] +
                            [{'date': through, 'all': cross_section(list(closes.values()))}]}}
    sources = {'indices': index_meta['content_digest'], 'sse_shares': share_meta['content_digest'],
               'szse_shares': szse_meta['content_digest'], 'risk': risk['content_digest'], 'closes': close_digests}
    result['snapshot_digest'] = digest({'base': data['snapshot_digest'], 'through': through, 'sources': sources})
    result['reading_update'] = {'base_through': data['requested_through'], 'through': through, 'sources': sources}
    broad = build_broad_etf_reading(result, root=folder)
    broad['capital_actions'] = capital_actions(root / 'trader_observations')
    if broad['as_of'] != through or broad['sample_funds'] != 12:
        raise ValueError('all six ETF/index groups required')
    watch = extend_watch(bases, closes, data['requested_through'], through)
    for basis in watch:
        if basis.get('availability') == 'available':
            basis['daily_close_extensions'] = [*basis.get('daily_close_extensions', []),
                                                {'through': through, 'source_digests': close_digests}]
    return result, watch, broad, sources


def replay(data, bases, raw, *, output=OUTPUT, root=MARKET_RISK_DIR, now=None):
    now = now or datetime.now(timezone.utc)
    if raw['version'] != VERSION or raw['base_binding'] != base_binding(data):
        raise ValueError('daily update base or implementation changed')
    checked = datetime.fromisoformat(raw['checked_at'])
    if checked.tzinfo is None or checked > now:
        raise ValueError('invalid daily update publication time')
    current, watch, broad = data, bases, None
    for step in raw['steps']:
        key = step['source_digest']
        if not re.fullmatch(r'[0-9a-f]{64}', key):
            raise ValueError('invalid daily source identity')
        folder = output / 'sources' / key
        if digest(source_files(folder)) != key:
            raise ValueError('daily source bytes changed')
        current, watch, broad, sources = project_step(current, watch, folder, step['through'], root=root, now=checked)
        if sources != step['bindings']:
            raise ValueError('daily close or membership binding changed')
    if not raw['steps'] or current['requested_through'] != raw['through']:
        raise ValueError('incomplete daily update chain')
    return current, watch, broad


def load_update(data, bases, *, output=OUTPUT, root=MARKET_RISK_DIR, now=None):
    """Read only; an invalid update must never replace a valid earlier reading."""
    pointer = output / 'current.json'
    if not pointer.exists():
        return None
    raw = bound_packet(pointer)
    if raw['processor_digest'] != processor_digest():
        raise ValueError('daily update implementation changed; explicit revalidation required')
    return replay(data, bases, raw, output=output, root=root, now=now)


def revalidate(data, bases, *, output=OUTPUT, root=MARKET_RISK_DIR):
    """Explicitly replay original sources after a software change; never rebind changed inputs."""
    processor = processor_digest()
    raw = bound_packet(output / 'current.json')
    replay(data, bases, raw, output=output, root=root)
    updated = {k: v for k, v in raw.items() if k != 'content_digest'}
    updated.update(processor_digest=processor, checked_at=datetime.now(timezone.utc).isoformat())
    if processor != processor_digest():
        raise ValueError('implementation changed during revalidation')
    updated['content_digest'] = digest(updated)
    atomic_write_json(output / 'snapshots' / (updated['content_digest'] + '.json'), updated)
    atomic_write_json(output / 'current.json', updated)
    return updated


def materialize(data, bases, inputs, through, *, output=OUTPUT, root=MARKET_RISK_DIR):
    processor = processor_digest(); existing = load_update(data, bases, output=output, root=root)
    previous = bound_packet(output / 'current.json') if existing else None
    current, watch = existing[:2] if existing else (data, bases)
    next_session(current['requested_through'], through)
    source_digest = digest(source_files(inputs)); target = output / 'sources' / source_digest
    for relative, expected in source_files(inputs).items():
        raw = (inputs / relative).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError('source changed during copy')
        dest = target / relative
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError('immutable daily source differs')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(raw)
    _, _, _, bindings = project_step(current, watch, target, through, root=root)
    raw = {'version': VERSION, 'processor_digest': processor, 'base_binding': base_binding(data),
           'through': through, 'steps': [*(previous['steps'] if previous else []),
                                       {'through': through, 'source_digest': source_digest, 'bindings': bindings}],
           'checked_at': datetime.now(timezone.utc).isoformat()}
    if processor_digest() != processor or digest(source_files(target)) != source_digest:
        raise ValueError('daily sources or code changed during publication')
    raw['content_digest'] = digest(raw)
    atomic_write_json(output / 'snapshots' / (raw['content_digest'] + '.json'), raw)
    atomic_write_json(output / 'current.json', raw)
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--through')
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--revalidate', action='store_true')
    args = parser.parse_args()
    if args.revalidate and (args.through or args.inputs) or not args.revalidate and not (args.through and args.inputs):
        parser.error('use either --revalidate or both --through and --inputs')
    from market_risk import build_market_risk_status
    from workbench_views import WATCHED, watch_basis
    data = build_market_risk_status()
    bases = [watch_basis(data, symbol) for symbol in WATCHED]
    value = revalidate(data, bases) if args.revalidate else materialize(data, bases, args.inputs, args.through)
    print(json.dumps({'through': value['through'], 'content_digest': value['content_digest']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
