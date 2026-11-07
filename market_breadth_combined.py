"""Source-bound SSE/SZSE breadth history with explicit full-day suspension reconciliation."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_breadth import cross_section
import market_breadth_history as szse
import sse_gap_review as notices
import sse_history_archive as sse

VERSION = 'combined_exchange_breadth_history_v1'
PLAN_PATH = Path(__file__).with_name('combined_breadth_plan_v1.json')
PLAN = json.loads(PLAN_PATH.read_text())
ROOT = sse.ROOT
OUTPUT = ROOT / 'combined_breadth_history'
API = 'https://query.sse.com.cn/commonSoaQuery.do'
SOURCE_URL = 'https://www.sse.com.cn/disclosure/dealinstruc/suspension/stock/'
SCRIPT_URL = 'https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_tradeTip_2021.js'


def processor_digest():
    return digest({'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), PLAN_PATH)},
                   'notices': notices.processor_digest(), 'szse': szse.processor_digest()})


PROCESSOR = processor_digest()


def query_params(code):
    return {'isPagination': 'true', 'sqlId': 'GW_PL_JYTS_TFPXX', 'pageHelp.pageSize': 100, 'pageHelp.pageNo': 1,
            'productCode': code, 'keyWords': '', 'startStopDate': PLAN['start'].replace('-', ''),
            'endStopDate': PLAN['through'].replace('-', '')}


def read_suspensions(capture, now):
    raw = json.loads((capture / 'complete.json').read_text())
    if (digest(raw) != PLAN['suspension_capture'] or raw['version'] != 'sse_suspend_interval_capture_v1'
        or (raw['start'], raw['through']) != (PLAN['start'], PLAN['through'])):
        raise ValueError('suspension source capture changed')
    refs = raw['source_refs']
    if sorted(r['kind'] for r in refs) != ['688121', '688496', 'all', 'stock_page', 'trade_tip']:
        raise ValueError('incomplete primary source and query checks')
    payloads = {}
    for ref in refs:
        observed = sse.stamp(ref['observed_at'], now)
        if observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() <= PLAN['through']:
            raise ValueError('source observation must follow the closed window')
        data = (capture / (ref['sha256'] + '.raw')).read_bytes()
        if len(data) != ref['bytes'] or hashlib.sha256(data).hexdigest() != ref['sha256']:
            raise ValueError('suspension source bytes changed')
        kind = ref['kind']
        if kind == 'stock_page':
            if ref['url'] != SOURCE_URL or 'js_suspension_stock' not in data.decode():
                raise ValueError('wrong official suspension page')
        elif kind == 'trade_tip':
            script = data.decode()
            if (ref['url'] != SCRIPT_URL or "suspensionUrl: sseQueryURL + 'commonSoaQuery.do'" not in script
                or "'GW_PL_JYTS_TFPXX'" not in script or "value == 'WH'" not in script or "return '全天'" not in script):
                raise ValueError('primary interface/time-field definition changed')
        else:
            code = '' if kind == 'all' else kind
            if ref['url'] != API or ref['params'] != query_params(code):
                raise ValueError('wrong or narrowed suspension query')
            j = json.loads(data)
            h = j['pageHelp']; rows = j['result']; total = h['total']
            if (j['sqlId'] != 'GW_PL_JYTS_TFPXX' or j['actionErrors'] != [] or j['fieldErrors'] != {}
                or j['isPagination'] != 'true' or h['data'] != rows or type(total) is not int or not 0 < total <= 100
                or h['pageNo'] != 1 or h['pageSize'] != 100 or h['pageCount'] != 1 or len(rows) != total):
                raise ValueError('partial, failed or differently paged suspension response')
            if code and any(r['productCode'] != code for r in rows):
                raise ValueError('targeted suspension lookup returned a foreign security')
            payloads[kind] = rows
    rows = payloads['all']
    if len({digest(r) for r in rows}) != len(rows):
        raise ValueError('duplicate suspension source record')
    for code in ('688121', '688496'):
        if [r for r in rows if r['productCode'] == code] != payloads[code]:
            raise ValueError('full report and individual lookups disagree')
    return rows, refs


def suspension_days(rows, basis, endpoint, notice_report):
    calendar = basis['window']['calendar']
    pairs, records, excluded = set(), [], Counter()
    open_starts = {e['symbol']: e['start_on'] for e in notice_report['episodes'] if e['kind'] == 'start_only'}
    for row in rows:
        code = row['productCode']
        if row['controlType'] != 'TR' or not re.fullmatch(r'(?:60|68)\d{4}', code):
            excluded['other_securities_or_business'] += 1
            continue
        if code not in basis['pool']:
            raise ValueError('ordinary-stock suspension absent from historical listing population')
        start = sse.ordinary_date(row['startStopDate'])
        end = sse.ordinary_date(row['endStopDate']) if row['endStopDate'] else None
        if end and end < start:
            raise ValueError('reversed suspension interval')
        if row['type'] == 'LSTP':
            if end != start:
                raise ValueError('temporary suspension is not a single date')
            if row['stopTime'] != 'WH':
                excluded['intraday'] += 1
                continue
        elif row['type'] != 'LXTP' or row['stopTime'] not in ('', 'WH'):
            raise ValueError('undeclared continuous suspension type/time')
        if end is None:
            if (open_starts.get(code) != start or endpoint.get(code, {}).get('is_trading') is not False
                or row['endStopReason'] != ''):
                raise ValueError('open exchange interval lacks matching notice start and inactive endpoint')
        days = [d for d in calendar if start <= d and (end is None or d <= end) and code in basis['populations'][d]]
        covered = {(d, code) for d in days}
        if not covered or pairs & covered:
            raise ValueError('non-overlapping in-window suspension records required')
        pairs |= covered
        records.append({'symbol': code, 'name_as_reported': row['productName'], 'start_on': start,
                        'last_suspended_on': end, 'kind': 'continuous' if row['type'] == 'LXTP' else 'full_day',
                        'open_when_observed': end is None, 'reason': row['stopReason'], 'end_reason': row['endStopReason'],
                        'window_days': days})
    # Notice evidence independently checks all 23 closed intervals; the exchange's
    # explicit continuous records provide the missing continuity for the other two.
    notice_pairs = {(d['date'], code[:6]) for d in notice_report['days'] for code in d['confirmed_suspended']}
    if not notice_pairs <= pairs:
        raise ValueError('exchange interval conflicts with reviewed notice dates')
    return pairs, {'source_rows': len(rows), 'ordinary_A_records': len(records), 'excluded': dict(excluded),
                   'notice_confirmed_days': len(notice_pairs), 'additional_continuous_days': len(pairs - notice_pairs), 'records': records}


def summarize_day(day, sse_rows, szse_rows):
    for suffix, rows in (('.SH', sse_rows), ('.SZ', szse_rows)):
        codes = [r['ts_code'] for r in rows]
        if len(set(codes)) != len(codes) or any(not c.endswith(suffix) for c in codes):
            raise ValueError('duplicate or foreign daily venue membership')
    return {'date': day, 'all': cross_section(sse_rows + szse_rows), 'SSE': cross_section(sse_rows), 'SZSE': cross_section(szse_rows)}


def collect_inputs(capture, *, root=ROOT, now=None, full=False):
    now = now or datetime.now(timezone.utc)
    if PLAN['sse_price_archive'] != notices.PROFILE['archive_digest']:
        raise ValueError('notice and combined price archive differ')
    proof = json.loads((root / 'sse_gap_review/snapshots' / (PLAN['sse_notice_review'] + '.json')).read_text())
    if (proof['processor_digest'] != notices.PROCESSOR or digest({k: v for k, v in proof.items() if k != 'content_digest'}) != PLAN['sse_notice_review']
        or proof['content_digest'] != PLAN['sse_notice_review']):
        raise ValueError('notice review snapshot changed')
    sse.stamp(proof['materialized_at'], now)
    ninputs = notices.collect_inputs(root=root, now=now, full=full)
    if digest(ninputs) != proof['input_digest']:
        raise ValueError('frozen notice inputs changed')
    notice_report = notices.project(ninputs)
    basis = ninputs['basis']; report = ninputs['archive']
    if (report['start'], report['through']) != (PLAN['start'], PLAN['through']):
        raise ValueError('source windows differ')
    rows, refs = read_suspensions(capture, now)
    pairs, stops = suspension_days(rows, basis, ninputs['endpoint'], notice_report)
    absent = {(d['date'], code[:6]) for d in report['days'] for code in d['not_returned'] + d['explicit_nontrading']}
    if pairs != absent:
        raise ValueError('suspension records do not explain every and only inactive/missing security-day')
    directory = root / 'sse_history_archive/sources' / notices.PROFILE['archive_input_digest']
    raw = json.loads((directory / 'full_prices/complete.json').read_text())
    by_day = defaultdict(dict)
    for ref in raw['source_refs']:
        records = sse.parse_prices(sse.body(directory / 'full_prices', ref, now), ref, basis, now)
        for day, row in records.items():
            if row['is_trading']:
                last, previous = float(row['last']), float(row['prev_close'])
                by_day[day][ref['code']] = {'ts_code': ref['code'] + '.SH', 'last': row['last'], 'prev_close': row['prev_close'],
                    'pct_chg': (last / previous - 1) * 100, 'amount': float(row['amount']), 'is_trading': True}
    hdir = root / 'public_breadth_history'
    hmeta = szse.load_breadth_history(hdir, now, snapshot_digest=PLAN['szse_history'])
    if hmeta['availability'] != 'observed' or (hmeta['start'], hmeta['through']) != (PLAN['start'], PLAN['through']):
        raise ValueError('complete frozen SZSE window unavailable')
    frozen = json.loads((hdir / 'snapshots' / (PLAN['szse_history'] + '.json')).read_text())
    if frozen['calendar'] != basis['window']['calendar']:
        raise ValueError('exchange calendars differ')
    points = []
    for day in frozen['calendar']:
        srows = []
        for code in basis['populations'][day]:
            row = by_day[day].get(code)
            if (row is None) != ((day, code) in pairs):
                raise ValueError('a traded quote conflicts with a full-day suspension')
            srows.append(row if row else {'ts_code': code + '.SH', 'is_trading': False})
        daily = szse._read_day(hdir, frozen['daily_snapshots'][day], day, now, check_raw=full, verify_hashes=True)
        points.append(summarize_day(day, srows, daily['block']['rows']))
    endpoint = sse.read_endpoint(root / 'public_breadth', basis['endpoint_digest'], PLAN['through'], now)
    if points[-1]['SSE'] != cross_section(list(endpoint.values())):
        raise ValueError('final-day breadth differs from independent closing cross-section')
    return {'points': points, 'suspensions': stops, 'source_refs': refs,
            'first_suspension_observed_at': min((r['observed_at'] for r in refs), key=datetime.fromisoformat),
            'fetched_at': max((r['observed_at'] for r in refs), key=datetime.fromisoformat),
            'sse_price_fetched_at': report['source_fetched_at'], 'szse_fetched_at': hmeta['fetched_at'],
            'sse_price_archive': PLAN['sse_price_archive'], 'szse_history': PLAN['szse_history'],
            'sse_notice_review': PLAN['sse_notice_review']}


def project(inputs):
    points = inputs['points']
    if [p['date'] for p in points] != sse.recent_calendar_window(PLAN['through'])['calendar']:
        raise ValueError('a partial window cannot be published')
    return {'availability': 'observed', 'scope': 'SSE_SZSE_ordinary_A_shares', 'start': PLAN['start'], 'through': PLAN['through'],
            'covered_venues': ['SSE', 'SZSE'], 'missing_venues': [], 'complete_market_history': True,
            'historical_ST_ready': False, 'historical_PIT': False, 'effect_measured': False,
            'observed_days': len(points), 'expected_days': len(points),
            'observation_count': sum(p['all']['listed_source_stocks'] for p in points),
            'traded_observation_count': sum(p['all']['observed_trading_stocks'] for p in points),
            'points': points, 'sse_suspensions': inputs['suspensions'],
            'fetched_at': inputs['fetched_at'], 'first_suspension_observed_at': inputs['first_suspension_observed_at'],
            'sse_price_fetched_at': inputs['sse_price_fetched_at'], 'szse_fetched_at': inputs['szse_fetched_at'],
            'source_refs': inputs['source_refs'], 'source_url': SOURCE_URL,
            'note': '沪深两所普通A股的逐日挂牌范围，保留期内上市和后来退出者；北交所、B股及优先股不在范围内。按收盘/官方前收参考价计算，停牌或无成交不算平盘，不填零收益。合并比例按有成交股票家数计算，不平均两所百分比。本次简称不回填历史ST成员，整体ST走势及风险效果仍需独立核验；资料本次取得不代表历史当时可见。'}


def history_status(directory=OUTPUT, *, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    base = {'version': VERSION, 'availability': 'missing', 'complete_market_history': False, 'historical_ST_ready': False,
            'historical_PIT': False, 'effect_measured': False, 'covered_venues': [], 'missing_venues': ['SSE', 'SZSE'], 'points': []}
    if processor_digest() != PROCESSOR:
        return {**base, 'availability': 'reload_required'}
    try:
        raw = json.loads((directory / 'current.json').read_text()); then = sse.stamp(raw['materialized_at'], now)
        if (raw['version'] != VERSION or raw['processor_digest'] != PROCESSOR
            or raw['capture_digest'] != PLAN['suspension_capture']
            or digest({k: v for k, v in raw.items() if k != 'content_digest'}) != raw['content_digest']):
            raise ValueError('combined history snapshot binding changed')
        inputs = collect_inputs(directory / 'sources' / raw['capture_digest'], root=root, now=then)
        if digest(inputs) != raw['input_digest']:
            raise ValueError('combined history sources changed')
        if processor_digest() != PROCESSOR:
            return {**base, 'availability': 'reload_required'}
        return {**base, **project(inputs), 'content_digest': raw['content_digest'], 'materialized_at': raw['materialized_at']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, ArithmeticError):
        return {**base, 'availability': 'invalid' if (directory / 'current.json').exists() else 'missing'}


def materialize(capture, *, output=OUTPUT, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    if processor_digest() != PROCESSOR:
        raise ValueError('reload changed code')
    if (output / 'current.json').exists() and json.loads((output / 'current.json').read_text()).get('version') != VERSION:
        raise ValueError('foreign output')
    inputs = collect_inputs(capture, root=root, now=now, full=True)
    result = project(inputs); target = output / 'sources' / PLAN['suspension_capture']
    for name in ['complete.json'] + [r['sha256'] + '.raw' for r in inputs['source_refs']]:
        data = (capture / name).read_bytes(); dest = target / name
        if dest.exists() and dest.read_bytes() != data:
            raise ValueError('immutable original differs')
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True); tmp = dest.with_suffix(dest.suffix + '.tmp'); tmp.write_bytes(data); tmp.replace(dest)
    if processor_digest() != PROCESSOR or collect_inputs(target, root=root, now=now, full=True) != inputs:
        raise ValueError('sources or code changed during publication')
    raw = {'version': VERSION, 'processor_digest': PROCESSOR, 'capture_digest': PLAN['suspension_capture'],
           'input_digest': digest(inputs), 'materialized_at': now.isoformat()}
    raw['content_digest'] = digest(raw)
    atomic_write_json(output / 'snapshots' / (raw['content_digest'] + '.json'), raw); atomic_write_json(output / 'current.json', raw)
    return {k: result[k] for k in ('availability', 'start', 'through', 'observed_days', 'observation_count', 'traded_observation_count')}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(materialize(args.capture), ensure_ascii=False)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
