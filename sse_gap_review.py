"""Reconcile missing SSE price dates against reviewed primary stop/resume notices."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
import sse_history_archive as archive

VERSION = 'sse_missing_day_reconciliation_v1'
PROFILE_PATH = Path(__file__).with_name('sse_gap_review_v1.json')
PROFILE = json.loads(PROFILE_PATH.read_text())
ROOT = archive.ROOT
OUTPUT = ROOT / 'sse_gap_review'


def processor_digest():
    return digest({'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (Path(__file__), PROFILE_PATH)}, 'archive': archive.processor_digest()})


PROCESSOR = processor_digest()


def compact(value):
    return re.sub(r'\s+', '', value)


def read_documents(folder, now, *, full=False):
    documents = {}
    for key, ref in PROFILE['documents'].items():
        raw = (folder / (ref['raw_sha256'] + '.pdf')).read_bytes()
        text = (folder / (ref['text_sha256'] + '.json')).read_bytes()
        pages = json.loads(text)['pages']
        observed = archive.stamp(ref['observed_at'], now)
        published = date.fromisoformat(ref['published_on'])
        if (not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest() != ref['raw_sha256']
            or hashlib.sha256(text).hexdigest() != ref['text_sha256']
            or len(raw) != ref['raw_bytes'] or len(text) != ref['text_bytes'] or len(pages) != ref['page_count']
            or not re.fullmatch(r'https://static\.cninfo\.com\.cn/finalpage/' + ref['published_on'] + r'/\d+\.PDF', ref['source_url'])
            or ref['final_url'] != ref['source_url']
            or published > observed.astimezone(ZoneInfo('Asia/Shanghai')).date()):
            raise ValueError('notice bytes, URL or availability changed')
        first = compact(pages[0])
        codes = {c for part in re.findall(r'(?:证券|股票)代码[:：]([0-9、，,]+)', first) for c in re.findall(r'\d{6}', part)}
        if ref['symbol'] not in codes or ref['company'] not in first:
            raise ValueError('notice company/security identity changed')
        if full:
            from pypdf import PdfReader
            if [page.extract_text() for page in PdfReader(BytesIO(raw)).pages] != pages:
                raise ValueError('notice extracted text disagrees with original PDF')
        documents[key] = {**ref, 'pages': pages}
    return documents


def verify_claim(claim, documents, episode):
    doc = documents[claim['document_id']]
    pages = claim['pages']
    if (doc['symbol'] != episode['symbol'] or doc['company'] != episode['company']
        or not pages or pages != sorted(set(pages)) or pages != list(range(pages[0], pages[-1] + 1))
        or any(type(p) is not int or not 1 <= p <= len(doc['pages']) for p in pages)):
        raise ValueError('claim identity/physical pages differ')
    quote = claim['quote']
    if not quote or quote != compact(quote) or quote not in ''.join(compact(doc['pages'][p-1]) for p in pages):
        raise ValueError('reviewed date-role clause not present')
    role = claim['role']
    if role == 'continuous_until_listing_end':
        if quote != '公司A股股票继续停牌直至终止上市。':
            raise ValueError('continuous stop role changed')
        return role, None
    day = date.fromisoformat(claim['effective_on'])
    token = f'{day.year}年{day.month}月{day.day}日'
    if token != claim['date_text'] or token not in quote:
        raise ValueError('claim date does not match its clause')
    if role == 'halt_start':
        if ('停牌' not in quote or '复牌' in quote or any(x in quote for x in ('预计', '可能', '拟', '午后', '下午', '盘中'))
            or claim['effective_on'] != episode['start_on']):
            raise ValueError('a forecast, intraday stop or unrelated date is not a full-day start')
    elif role == 'resume':
        if ('复牌' not in quote or '停牌' in quote or any(x in quote for x in ('预计', '可能', '拟', '不再', '无法'))
            or claim['effective_on'] != episode['end_exclusive']):
            raise ValueError('resume date/direction changed')
    else:
        raise ValueError('undeclared date role')
    return role, claim['effective_on']


def collect_inputs(*, root=ROOT, now=None, full=False):
    now = now or datetime.now(timezone.utc)
    directory = root / 'sse_history_archive'
    frozen = json.loads((directory / 'snapshots' / (PROFILE['archive_digest'] + '.json')).read_text())
    if (frozen['version'] != archive.VERSION or frozen['processor_digest'] != PROFILE['archive_processor_digest']
        or archive.processor_digest() != PROFILE['archive_processor_digest']
        or frozen['input_digest'] != PROFILE['archive_input_digest']
        or digest({k: v for k, v in frozen.items() if k != 'content_digest'}) != PROFILE['archive_digest']
        or frozen['content_digest'] != PROFILE['archive_digest']):
        raise ValueError('frozen source archive binding changed')
    then = archive.stamp(frozen['materialized_at'], now)
    capture = directory / 'sources' / frozen['input_digest']
    if archive.input_key(capture) != frozen['input_digest']:
        raise ValueError('frozen source index changed')
    report = archive.project(capture, root / 'public_breadth', then)
    if (report['start'], report['through']) != (PROFILE['start'], PROFILE['through']):
        raise ValueError('reviewed source window changed')
    basis = archive.read_basis(capture, then)
    refs = json.loads((capture / 'full_prices/complete.json').read_text())['source_refs']
    symbols = {e['symbol'] for e in PROFILE['episodes']}
    prices = {r['code']: archive.parse_prices(archive.body(capture / 'full_prices', r, then), r, basis, then)
              for r in refs if r['code'] in symbols}
    endpoint = archive.read_endpoint(root / 'public_breadth', basis['endpoint_digest'], PROFILE['through'], then)
    documents = read_documents(root / 'sse_gap_review/documents', now, full=full)
    # The report, prices and listing populations all come from the frozen raw archive,
    # rather than a later current pointer or a hand-entered gap count.
    return {'archive': report, 'archive_materialized_at': frozen['materialized_at'], 'basis': basis,
            'prices': prices, 'endpoint': {c: endpoint[c] for c in symbols if c in endpoint}, 'documents': documents}


def project(inputs):
    report, basis, prices = (inputs[k] for k in ('archive', 'basis', 'prices'))
    missing = {(d['date'], code[:6]) for d in report['days'] for code in d['not_returned']}
    inactive = {(d['date'], code[:6]) for d in report['days'] for code in d['explicit_nontrading']}
    explained, reviewed, episodes = set(), set(), []
    ids = set()
    for item in PROFILE['episodes']:
        code, start, end, kind = (item[k] for k in ('symbol', 'start_on', 'end_exclusive', 'kind'))
        if item['case_id'] in ids or date.fromisoformat(start).isoformat() != start or code not in basis['pool']:
            raise ValueError('duplicate or foreign episode')
        ids.add(item['case_id'])
        claims = [verify_claim(c, inputs['documents'], item) for c in item['claims']]
        roles = [c[0] for c in claims]
        expected = {'resumed': ['halt_start', 'resume'], 'one_day': ['halt_start'],
                    'continuous_to_listing_end': ['halt_start', 'continuous_until_listing_end'], 'start_only': ['halt_start']}
        if roles != expected.get(kind) or (end is not None and (date.fromisoformat(end).isoformat() != end or end <= start)):
            raise ValueError('episode direction, bounds or required date roles differ')
        if kind == 'continuous_to_listing_end' and basis['pool'][code]['ended_on'] != end:
            raise ValueError('continuous stop must end at the actual registry termination, not a resume')
        if kind == 'one_day':
            following = next((d for d in basis['window']['calendar'] if d > start), None)
            if end != following or not re.search(r'停牌(?:一日|一天|1天)', item['claims'][0]['quote']):
                raise ValueError('one-day stop is not explicit')
        if kind == 'start_only':
            if end is not None or inputs['endpoint'].get(code, {}).get('is_trading') is not False:
                raise ValueError('open stop must have no asserted end and an independently inactive endpoint')
        elif end is None:
            raise ValueError('closed stop needs an exclusive endpoint')
        if kind == 'resumed' and (end not in prices[code] or not prices[code][end]['is_trading']):
            raise ValueError('announced resumption lacks an actual in-window traded quote')
        days = [d for d, members in basis['populations'].items() if start <= d and (end is None or d < end) and code in members]
        pairs = {(d, code) for d in days}
        if not pairs or any(prices[code].get(d, {}).get('is_trading') for d in days):
            raise ValueError('reviewed stop interval conflicts with actual trades')
        if reviewed & pairs or not pairs <= missing | inactive:
            raise ValueError('overlapping episode or unexplained observation category')
        reviewed |= pairs
        closed = kind != 'start_only'
        if closed:
            explained |= pairs
        episodes.append({k: item[k] for k in ('case_id', 'symbol', 'company', 'kind', 'start_on', 'end_exclusive')} | {
            'interval_closed': closed, 'window_days': days, 'confirmed_missing_days': len(pairs & missing) if closed else 0,
            'unresolved_missing_days': 0 if closed else len(pairs & missing),
            'endpoint_nontrading_confirmed': not inputs['endpoint'].get(code, {}).get('is_trading', True) if not closed else None,
            'proofs': [{'source_url': inputs['documents'][c['document_id']]['source_url'], 'pages': c['pages'], 'role': c['role'],
                        'published_on': inputs['documents'][c['document_id']]['published_on'],
                        'observed_at': inputs['documents'][c['document_id']]['observed_at']} for c in item['claims']]})
    unresolved = missing - explained
    return {'availability': 'observed' if not unresolved else 'partial', 'start': report['start'], 'through': report['through'],
            'archive_digest': PROFILE['archive_digest'], 'reviewed_episodes': len(episodes),
            'distinct_companies': len({e['symbol'] for e in episodes}), 'closed_episodes': sum(e['interval_closed'] for e in episodes),
            'original_pdfs': len(inputs['documents']), 'not_returned_days': len(missing),
            'confirmed_missing_days': len(explained & missing), 'unresolved_missing_days': len(unresolved),
            'unreviewed_missing_days': len(missing - reviewed), 'episodes': episodes,
            'historical_breadth_ready': not unresolved, 'historical_ST_ready': False, 'historical_PIT': False, 'effect_measured': False,
            'source_fetched_at': max((d['observed_at'] for d in inputs['documents'].values()), key=datetime.fromisoformat),
            'days': [{'date': d['date'], 'confirmed_suspended': sorted(c + '.SH' for day, c in explained & missing if day == d['date']),
                      'unresolved': sorted(c + '.SH' for day, c in unresolved if day == d['date'])} for d in report['days']],
            'note': '仅完整区间的公告依据用于解释缺日；仅有停牌起点及期末停牌状态不推断整个中间区间。终止上市日不作复牌日，停牌不填零收益；公告发布日与本次取得日分开记录。历史ST成员和风险效果仍需独立核验。'}


def review_status(directory=OUTPUT, *, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    base = {'version': VERSION, 'availability': 'missing', 'historical_breadth_ready': False,
            'historical_ST_ready': False, 'historical_PIT': False, 'effect_measured': False}
    if processor_digest() != PROCESSOR:
        return {**base, 'availability': 'reload_required'}
    try:
        raw = json.loads((directory / 'current.json').read_text())
        then = archive.stamp(raw['materialized_at'], now)
        if (raw['version'] != VERSION or raw['processor_digest'] != PROCESSOR
            or digest({k: v for k, v in raw.items() if k != 'content_digest'}) != raw['content_digest']):
            raise ValueError('review snapshot binding changed')
        inputs = collect_inputs(root=root, now=then)
        if digest(inputs) != raw['input_digest']:
            raise ValueError('review inputs changed')
        if processor_digest() != PROCESSOR:
            return {**base, 'availability': 'reload_required'}
        return {**base, **project(inputs), 'content_digest': raw['content_digest'], 'materialized_at': raw['materialized_at']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, ArithmeticError):
        return {**base, 'availability': 'invalid' if (directory / 'current.json').exists() else 'missing'}


def materialize(*, output=OUTPUT, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    if processor_digest() != PROCESSOR:
        raise ValueError('reload changed processor')
    if (output / 'current.json').exists() and json.loads((output / 'current.json').read_text()).get('version') != VERSION:
        raise ValueError('foreign output')
    inputs = collect_inputs(root=root, now=now, full=True)
    result = project(inputs)
    raw = {'version': VERSION, 'processor_digest': PROCESSOR, 'input_digest': digest(inputs), 'materialized_at': now.isoformat()}
    if processor_digest() != PROCESSOR or digest(collect_inputs(root=root, now=now)) != raw['input_digest']:
        raise ValueError('processor or sources changed during materialization')
    raw['content_digest'] = digest(raw)
    atomic_write_json(output / 'snapshots' / (raw['content_digest'] + '.json'), raw)
    atomic_write_json(output / 'current.json', raw)
    return {k: result[k] for k in ('availability', 'reviewed_episodes', 'closed_episodes', 'confirmed_missing_days', 'unresolved_missing_days')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(materialize(output=args.output), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
