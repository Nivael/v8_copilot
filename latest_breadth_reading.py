"""Replay complete official daily pages before publishing a separate breadth date."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from market_breadth import SOURCES, SSE_SELECT, load_public_breadth
from market_breadth_refresh import parse_sse, parse_szse
from market_breadth_export import EXPORT_KIND, EXPORT_URL, export_params, parse_export
from settings import DATA_ROOT
from exchange_risk_membership import SZSE_API as SZSE_CONTROL_API

OUTPUT = DATA_ROOT / 'local_data/v8_copilot/market_risk/trader_observations/latest_breadth'


def verified_breadth(directory: Path, *, now=None):
    now = now or datetime.now(timezone.utc)
    meta, result = load_public_breadth(directory, now)
    if meta['availability'] != 'observed':
        raise ValueError('complete breadth snapshot required')
    packet = json.loads((directory / 'current.json').read_text())
    through = packet['requested_through']
    refs = {'SSE': [], 'SZSE': []}
    for ref in packet['responses']:
        if ref['venue'] not in refs:
            raise ValueError('unexpected breadth venue')
        refs[ref['venue']].append(ref)
    def original(ref, url, params, *, export=False):
        if ref['url'] != url or ref['params'] != params or (export and ref.get('kind') != EXPORT_KIND):
            raise ValueError('breadth source or query changed')
        observed = datetime.fromisoformat(ref['observed_at'])
        if observed.tzinfo is None or observed > now or observed.date().isoformat() < through:
            raise ValueError('invalid breadth observation time')
        key = ref['response_sha256']
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('invalid breadth response identity')
        body = (directory / 'responses' / (key + ('.xlsx' if export else '.json'))).read_bytes()
        if len(body) != ref['bytes'] or sha256(body).hexdigest() != key:
            raise ValueError('breadth original changed')
        return body if export else json.loads(body)
    if not all(refs.values()):
        raise ValueError('both complete exchange originals required')
    sse_pages = [original(ref, SOURCES['SSE']['api_url'],
                 {'select': SSE_SELECT, 'begin': i * 500, 'end': (i + 1) * 500}) for i, ref in enumerate(refs['SSE'])]
    params = {'SHOWTYPE': 'JSON', 'CATALOGID': SOURCES['SZSE']['catalog'], 'TABKEY': 'tab1',
              'txtBeginDate': through, 'txtEndDate': through}
    if any(ref.get('kind') == EXPORT_KIND for ref in refs['SZSE']):
        if len(refs['SZSE']) != 3:
            raise ValueError('exact export and two boundary controls required')
        head = original(refs['SZSE'][0], SOURCES['SZSE']['api_url'], {**params, 'PAGENO': 1})
        count = head[0]['metadata']['pagecount']
        tail_ref = refs['SZSE'][1]
        if tail_ref['url'] not in (SOURCES['SZSE']['api_url'], SZSE_CONTROL_API):
            raise ValueError('unexpected export tail control source')
        tail = original(tail_ref, tail_ref['url'], {**params, 'PAGENO': count})
        body = original(refs['SZSE'][2], EXPORT_URL, export_params(through), export=True)
        szse = parse_export(body, head, tail, through)
    else:
        szse = parse_szse([original(ref, SOURCES['SZSE']['api_url'], {**params, 'PAGENO': i + 1})
                          for i, ref in enumerate(refs['SZSE'])], through)
    for venue, parsed in [('SSE', parse_sse(sse_pages, through)), ('SZSE', szse)]:
        if parsed != packet['venues'][venue]:
            raise ValueError('breadth projection differs from original pages')
    def group(label, values):
        total = values['observed_trading_stocks']
        return {'name': label, **{key: values[key] for key in ('listed_source_stocks', 'observed_trading_stocks',
                'nontrading_stocks', 'advancing', 'declining', 'flat', 'declining_5pct_or_more', 'median_return_pct')},
                'advancing_pct': values['advancing'] / total * 100 if total else None,
                'declining_5pct_or_more_pct': values['declining_5pct_or_more'] / total * 100 if total else None}
    return {'availability': 'available', 'as_of': through, 'source_digest': meta['content_digest'],
            'observed_at': max(ref['observed_at'] for ref in packet['responses']),
            'source_file_count': len(packet['responses']),
            'szse_acquisition': 'official_xlsx_with_dated_boundary_controls' if any(r.get('kind') == EXPORT_KIND for r in refs['SZSE']) else 'complete_https_json_pages',
            'scope': 'SSE_SZSE_A_shares_not_BSE', 'return_basis': result['return_basis'],
            'groups': [group('沪深A股', result), group('当日ST简称组', result['st_name_group'])],
            'sources': [{'label': s['label'], 'url': s['url']} for s in SOURCES.values()],
            'transport_note': '首控制页为HTTPS；末控制页和完整Excel使用官方HTTP地址，未声称全部原件经HTTPS取得。' if any(r['url'].startswith('http:') for r in packet['responses']) else '原件均经HTTPS取得。',
            'limits': ['跌幅至少5%只是固定幅度分布，不是跌停家数；不同板块及特殊交易日限制尚未逐股核验。',
                       '无成交股票不计作平盘，不进入涨跌比例分母；不含北交所。',
                       'ST只是当日简称分组，未据此认证独立风险名单或连续历史成员。',
                       '单日截面不能说明连续恶化、连续跌停、均线覆盖或实际可退出性。']}


def newer_breadth(base, *, directory=OUTPUT, now=None):
    try:
        result = verified_breadth(directory, now=now)
        return result if result['as_of'] > base['as_of'] else None
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
