"""Descriptive two-venue ST reconstruction; SSE daily membership is not independently certified."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
import market_breadth_combined as breadth
from market_breadth import st_name
import sse_history_archive as sse
import szse_st_reference as szse
from settings import MARKET_CONTEXT_DB

VERSION = 'combined_ST_reconstructed_price_reference_v1'
PLAN_PATH = Path(__file__).with_name('combined_st_reference_plan_v1.json')
EVENT_PATH = Path(__file__).with_name('sse_st_transitions_v1.json')
TRIAGE_PATH = Path(__file__).with_name('sse_st_catalog_triage_v1.json')
PLAN = json.loads(PLAN_PATH.read_text())
EVENTS = json.loads(EVENT_PATH.read_text())['events']
TRIAGE = json.loads(TRIAGE_PATH.read_text())
ROOT = sse.ROOT
OUTPUT = ROOT / 'st_reconstruction'


def processor_digest():
    return digest({'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            (Path(__file__), PLAN_PATH, EVENT_PATH, TRIAGE_PATH)},
                   'breadth': breadth.processor_digest(), 'szse': szse.processor_digest()})


PROCESSOR = processor_digest()


def frozen(directory, key, version, processor, now):
    raw = json.loads((directory / 'snapshots' / (key + '.json')).read_text())
    if (raw['version'] != version or raw['processor_digest'] != processor or raw['content_digest'] != key
        or digest({k: v for k, v in raw.items() if k != 'content_digest'}) != key):
        raise ValueError('frozen source binding changed')
    sse.stamp(raw['materialized_at'], now)
    return raw


def sse_proofs(folder, now, *, full=False):
    events = []
    for item in EVENTS:
        raw = (folder / (item['raw_sha256'] + '.pdf')).read_bytes()
        text = (folder / (item['text_sha256'] + '.json')).read_bytes()
        if (not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest() != item['raw_sha256']
            or hashlib.sha256(text).hexdigest() != item['text_sha256']
            or len(raw) != item['raw_bytes'] or len(text) != item['text_bytes']):
            raise ValueError('SSE notice original bytes changed')
        pages = json.loads(text)['pages']; first = szse.compact(pages[0]); page = szse.compact(pages[item['proof_page']-1])
        observed = sse.stamp(item['observed_at'], now)
        codes = {c for group in re.findall(r'证券代码[:：]([0-9、，,]+)', first) for c in re.findall(r'\d{6}', group)}
        if (len(pages) != item['page_count']
            or item['symbol'] not in codes or item['company'] not in first or item['old_name'] not in first
            or item['published_on'] > item['effective_on'] or date.fromisoformat(item['published_on']) > observed.astimezone(ZoneInfo('Asia/Shanghai')).date()
            or not re.fullmatch(r'https://static\.cninfo\.com\.cn/finalpage/' + item['published_on'] + r'/\d+\.PDF', item['source_url'])):
            raise ValueError('SSE notice bytes, identity or availability changed')
        pattern = re.escape(item['date_label']) + r'[:：](20\d{2})年(\d{1,2})月(\d{1,2})日'
        dates = {date(*map(int, parts)).isoformat() for parts in re.findall(pattern, page)}
        direction = r'(?:股票|证券)简称[:：]?由[“"]?' + re.escape(item['old_name']) + r'[”"]?变更为[“"]?' + re.escape(item['new_name']) + r'[”"]?'
        if dates != {item['effective_on']} or not re.search(direction, page):
            raise ValueError('SSE effective-date role or name direction not matched')
        if (item['kind'] not in ('warning_added', 'warning_removed')
            or st_name(item['old_name']) != (item['kind'] == 'warning_removed')
            or st_name(item['new_name']) != (item['kind'] == 'warning_added')):
            raise ValueError('SSE membership direction changed')
        if full:
            from pypdf import PdfReader
            if [p.extract_text() for p in PdfReader(BytesIO(raw)).pages] != pages:
                raise ValueError('SSE extracted text differs from original PDF')
        events.append(dict(item))
    return events


def title_triage(folder, now):
    ref = TRIAGE['source_ref']; sse.stamp(ref['observed_at'], now)
    raw = (folder / (ref['sha256'] + '.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256'] or len(raw) != ref['bytes']:
        raise ValueError('catalog bytes changed')
    source = json.loads(raw); items = [r for group in source['result'] for r in group]
    if (ref['url'] != 'https://query.sse.com.cn/security/stock/queryCompanyBulletinNew.do'
        or ref['params']['TITLE'] != '风险警示' or ref['params']['SECURITY_CODE'] != ''
        or (ref['params']['START_DATE'], ref['params']['END_DATE']) != ('2026-09-01', PLAN['through'])
        or source['pageHelp']['pageCount'] != 1 or source['pageHelp']['total'] != len(items)
        or len(items) != len(TRIAGE['items'])):
        raise ValueError('catalog scope or completeness changed')
    for row, item in zip(items, TRIAGE['items'], strict=True):
        if (row['SECURITY_CODE'], row['SSEDATE'], row['TITLE'], 'https://www.sse.com.cn' + row['URL']) != (
            item['symbol'], item['published_on'], item['title'], item['catalog_url']):
            raise ValueError('title triage does not match the original catalog')
    selected = {(r['symbol'], r['published_on']) for r in TRIAGE['items'] if r['triage'] == 'effective_transition_with_primary_date_clause'}
    if selected != {(e['symbol'], e['published_on']) for e in EVENTS}:
        raise ValueError('selected effective notices differ from catalog triage')
    return {'items': TRIAGE['items'], 'review_level': TRIAGE['level'], 'observed_at': ref['observed_at'],
            'full_body_review': False, 'daily_membership_certificate': False}


def collect_inputs(*, root=ROOT, market_db=MARKET_CONTEXT_DB, now=None, full=False):
    now = now or datetime.now(timezone.utc)
    bdir = root / 'combined_breadth_history'
    braw = frozen(bdir, PLAN['combined_breadth'], breadth.VERSION, breadth.PROCESSOR, now)
    bi = breadth.collect_inputs(bdir / 'sources' / braw['capture_digest'], root=root, now=now, full=full)
    if digest(bi) != braw['input_digest'] or breadth.project(bi)['availability'] != 'observed':
        raise ValueError('complete frozen price/suspension window changed')
    zraw = frozen(root / 'szse_st_reference', PLAN['szse_reference'], szse.VERSION, szse.PROCESSOR, now)
    zi = szse.collect_inputs(root=root, market_db=market_db, now=now, full=full)
    if digest(zi) != zraw['input_digest']:
        raise ValueError('frozen SZSE reference inputs changed')
    zreport = szse.project(zi)
    if zreport['availability'] != 'observed' or (zreport['start'], zreport['through']) != (PLAN['start'], PLAN['through']):
        raise ValueError('complete independently checked SZSE sample unavailable')
    with closing(sqlite3.connect(market_db.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        anchor = [dict(r) for r in conn.execute('select trade_date,symbol,ts_code,name,risk_type,risk_type_name,source,fetched_at '
                   'from st_membership_daily where trade_date=? and ts_code like ? order by ts_code', (PLAN['anchor_on'], '%.SH'))]
    if len(anchor) != PLAN['sse_anchor_members'] or digest(anchor) != PLAN['sse_anchor_digest']:
        raise ValueError('dated SSE membership anchor changed')
    for row in anchor:
        sse.stamp(row['fetched_at'], now)
        if not re.fullmatch(r'(?:60|68)\d{4}\.SH', row['ts_code']) or row['source'] != 'tushare:stock_st' or not st_name(row['name']):
            raise ValueError('SSE anchor identity/scope changed')
    documents = sse_proofs(root / 'st_reconstruction/documents', now, full=full)
    triage = title_triage(root / 'st_reconstruction/catalog', now)
    adir = root / 'sse_history_archive/sources' / breadth.notices.PROFILE['archive_input_digest']
    basis = sse.read_basis(adir, now); codes = {r['symbol'] for r in anchor} | {e['symbol'] for e in documents}
    raw = json.loads((adir / 'full_prices/complete.json').read_text())
    prices = {r['code']: sse.parse_prices(sse.body(adir / 'full_prices', r, now), r, basis, now)
              for r in raw['source_refs'] if r['code'] in codes}
    endpoint = sse.read_endpoint(root / 'public_breadth', basis['endpoint_digest'], PLAN['through'], now)
    endpoint_members = sorted(c + '.SH' for c, r in endpoint.items() if st_name(r['security_name']))
    rdir = root / 'exchange_risk_membership'
    riskraw = json.loads((rdir / 'snapshots' / (PLAN['risk_list'] + '.json')).read_text())
    if digest({k: v for k, v in riskraw.items() if k != 'content_digest'}) != PLAN['risk_list']:
        raise ValueError('independent endpoint list changed')
    risk = szse.risk_lists.project(riskraw, rdir, now)
    separate_members = sorted(r['ts_code'] for r in risk['rows'] if r['venue'] == 'SSE' and r['kind'] == 'risk_warning' and r['share_class'] == 'A')
    if endpoint_members != separate_members:
        raise ValueError('endpoint quote-name group and separately observed exchange list disagree')
    return {'anchor': anchor, 'events': documents, 'catalog': triage, 'sse_prices': prices,
            'sse_populations': basis['populations'], 'sse_endpoint_members': endpoint_members,
            'endpoint_list_observed_on': risk['observed_on'], 'szse_days': zi['days'], 'szse_reference': zreport,
            'calendar': basis['window']['calendar'],
            'confirmed_sse_suspensions': {d: sorted(r['symbol'] + '.SH' for r in bi['suspensions']['records'] if d in r['window_days']) for d in basis['window']['calendar']},
            'sse_price_fetched_at': bi['sse_price_fetched_at'], 'szse_price_fetched_at': zi['history_fetched_at'],
            'newest_notice_observed_at': max((e['observed_at'] for e in documents), key=datetime.fromisoformat)}


def sample(members, rows):
    values, missing = [], []
    for code in sorted(members):
        row = rows.get(code)
        if row is None or not row['is_trading']:
            missing.append(code); continue
        last, previous = Decimal(str(row['last'])), Decimal(str(row['prev_close']))
        if not last.is_finite() or not previous.is_finite() or min(last, previous) <= 0:
            raise ValueError('active ST member lacks a valid price/reference')
        values.append((last / previous - 1) * 100)
    return {'member_count': len(members), 'observed_members': len(values), 'coverage_ratio': len(values) / len(members) if members else 0,
            'missing_symbols': missing, 'daily_return_pct': float(sum(values) / len(values)) if values else None}, values


def project(inputs):
    calendar = inputs['calendar']; zdays = inputs['szse_days']
    if (calendar != sse.recent_calendar_window(PLAN['through'])['calendar'] or calendar[0] != PLAN['start']
        or [d['date'] for d in zdays] != calendar):
        raise ValueError('full matching ST reference calendars required')
    members = {r['ts_code']: r['name'] for r in inputs['anchor']}; ever = set(members); points = []; memberships = []
    keyed = {(e['effective_on'], e['symbol'] + '.SH'): e for e in inputs['events']}
    if len(keyed) != len(inputs['events']) or any(day not in calendar for day, _ in keyed):
        raise ValueError('duplicate or outside SSE transition')
    seen = set()
    for day, zd in zip(calendar, zdays, strict=True):
        for (effective, code), event in keyed.items():
            if effective != day: continue
            if event['kind'] == 'warning_added':
                if code in members or st_name(event['old_name']) or not st_name(event['new_name']): raise ValueError('invalid SSE membership addition')
                members[code] = event['new_name']; ever.add(code)
            elif event['kind'] == 'warning_removed':
                if members.get(code) != event['old_name'] or st_name(event['new_name']): raise ValueError('invalid SSE membership removal')
                members.pop(code)
            else: raise ValueError('unreviewed SSE transition type')
            seen.add((effective, code))
        if not {c[:6] for c in members} <= set(inputs['sse_populations'][day]):
            raise ValueError('ST reconstruction includes an unlisted/exited SSE security')
        sr = {c: inputs['sse_prices'][c[:6]].get(day) for c in members}
        for code, row in sr.items():
            if (row is None or not row['is_trading']) and code not in inputs['confirmed_sse_suspensions'][day]:
                raise ValueError('missing SSE ST price lacks verified full-day suspension')
        zr = {r['ts_code']: r for r in zd['rows']}
        if len(zr) != len(zd['rows']) or len(set(zd['source_marked'])) != len(zd['source_marked']): raise ValueError('duplicate SZSE price/member row')
        sm, sv = sample(members, sr); zm, zv = sample(set(zd['source_marked']), zr)
        values = sv + zv; total = len(members) + len(zd['source_marked'])
        allm = {'member_count': total, 'observed_members': len(values), 'coverage_ratio': len(values) / total if total else 0,
                'missing_symbols': sorted(sm['missing_symbols'] + zm['missing_symbols']),
                'daily_return_pct': float(sum(values) / len(values)) if values else None}
        points.append({'date': day, 'all': allm, 'SSE': sm, 'SZSE': zm})
        memberships.append({'date': day, 'SSE': sorted(members), 'SZSE': sorted(zd['source_marked'])})
    if seen != set(keyed) or sorted(members) != inputs['sse_endpoint_members']:
        raise ValueError('SSE events or endpoint do not reconcile')
    ready = all(p[g]['coverage_ratio'] >= PLAN['minimum_daily_coverage'] and p[g]['daily_return_pct'] is not None
                for p in points for g in ('all', 'SSE', 'SZSE'))
    metrics = {}
    for group in ('all', 'SSE', 'SZSE'):
        level = 1000.; peak = 0.; drawdown = 0.
        for p in points:
            if ready:
                level *= 1 + p[group]['daily_return_pct'] / 100; peak = max(peak, level)
                drawdown = min(drawdown, (level / peak - 1) * 100); p[group]['close'] = round(level, 8)
            else: p[group]['close'] = None
        metrics[group] = {'return_pct': (points[-1][group]['close'] / points[0][group]['close'] - 1) * 100 if ready else None,
                          'max_drawdown_pct': drawdown if ready else None, 'minimum_coverage': min(p[group]['coverage_ratio'] for p in points),
                          'member_day_observations': sum(p[group]['member_count'] for p in points),
                          'observed_member_days': sum(p[group]['observed_members'] for p in points)}
    return {'availability': 'reconstructed' if ready else 'insufficient_coverage', 'start': PLAN['start'], 'through': PLAN['through'],
            'source_venues': ['SSE', 'SZSE'], 'verified_daily_membership_venues': ['SZSE'], 'reconstructed_membership_venues': ['SSE'],
            'combined_ST_ready': False, 'historical_membership_verified': False, 'historical_PIT': False, 'portfolio_wealth': False, 'effect_measured': False,
            'coverage_threshold': PLAN['minimum_daily_coverage'], 'points': points, 'metrics': metrics, 'memberships': memberships,
            'sse_anchor_members': len(inputs['anchor']), 'sse_distinct_members': len(ever), 'sse_endpoint_members': len(members),
            'sse_reviewed_transitions': len(inputs['events']), 'szse_reviewed_transitions': inputs['szse_reference']['reviewed_transitions'],
            'szse_distinct_members': inputs['szse_reference']['distinct_members'], 'szse_endpoint_members': inputs['szse_reference']['endpoint_members'],
            'endpoint_list_observed_on': inputs['endpoint_list_observed_on'], 'events': inputs['events'], 'catalog': inputs['catalog'],
            'sse_price_fetched_at': inputs['sse_price_fetched_at'], 'szse_price_fetched_at': inputs['szse_price_fetched_at'],
            'newest_notice_observed_at': inputs['newest_notice_observed_at'],
            'note': '沪深ST回溯重建的有成交样本价格参考。沪市由日期锚点和已核公告重建，目录仅做标题筛查，尚无完整逐日名单/简称的独立交叉核验；期初期末相符不证明中间无遗漏。每日有成交成员等权合并，不平均两所均值，停牌保留分母且不填零。成员和成交样本变化，路径不是组合财富、全收益、已完整核验的ST指数或可交易回报；不校准风险权重，也不证明大盘因素优于节点。'}


def reference_status(directory=OUTPUT, *, root=ROOT, market_db=MARKET_CONTEXT_DB, now=None):
    now = now or datetime.now(timezone.utc)
    base = {'version': VERSION, 'availability': 'missing', 'combined_ST_ready': False, 'historical_membership_verified': False,
            'historical_PIT': False, 'portfolio_wealth': False, 'effect_measured': False, 'points': []}
    if processor_digest() != PROCESSOR: return {**base, 'availability': 'reload_required'}
    try:
        raw = json.loads((directory / 'current.json').read_text()); then = sse.stamp(raw['materialized_at'], now)
        if (raw['version'] != VERSION or raw['processor_digest'] != PROCESSOR
            or digest({k: v for k, v in raw.items() if k != 'content_digest'}) != raw['content_digest']):
            raise ValueError('ST reconstruction binding changed')
        inputs = collect_inputs(root=root, market_db=market_db, now=then)
        if digest(inputs) != raw['input_digest']: raise ValueError('ST reconstruction inputs changed')
        if processor_digest() != PROCESSOR: return {**base, 'availability': 'reload_required'}
        return {**base, **project(inputs), 'content_digest': raw['content_digest'], 'materialized_at': raw['materialized_at']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, sqlite3.Error, ArithmeticError):
        return {**base, 'availability': 'invalid' if (directory / 'current.json').exists() else 'missing'}


def materialize(*, output=OUTPUT, root=ROOT, market_db=MARKET_CONTEXT_DB, now=None):
    now = now or datetime.now(timezone.utc)
    if processor_digest() != PROCESSOR: raise ValueError('reload changed code')
    if (output / 'current.json').exists() and json.loads((output / 'current.json').read_text()).get('version') != VERSION: raise ValueError('foreign output')
    inputs = collect_inputs(root=root, market_db=market_db, now=now, full=True); result = project(inputs)
    raw = {'version': VERSION, 'processor_digest': PROCESSOR, 'input_digest': digest(inputs), 'materialized_at': now.isoformat()}
    if processor_digest() != PROCESSOR or digest(collect_inputs(root=root, market_db=market_db, now=now)) != raw['input_digest']:
        raise ValueError('ST reconstruction sources or code changed')
    raw['content_digest'] = digest(raw); atomic_write_json(output / 'snapshots' / (raw['content_digest'] + '.json'), raw); atomic_write_json(output / 'current.json', raw)
    return {'availability': result['availability'], 'metrics': result['metrics'], 'sse_distinct_members': result['sse_distinct_members']}


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args(); print(json.dumps(materialize(), ensure_ascii=False))
