"""Independently bound prices around an older original; never splice global paths."""
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode
import re

from canonical_json import digest

VERSION = 'history_question_period_sources_v1'
GAP_NOTE = '来源未提供这一天的有效报价；原因未核定，保持空档。'


def question_period_paths(value, *, symbol, asked_on):
    if (not isinstance(value, dict) or value.get('version') != VERSION
            or value.get('price_basis') != 'supplier_qfq_price_not_total_return'
            or value.get('symbol') != symbol
            or not re.fullmatch(r'(?:[03]\d{5}\.SZ|6\d{5}\.SH)', symbol)
            or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value.get('content_digest')):
        raise ValueError('question period source binding changed')
    for key in ('title', 'summary', 'source_note'):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError('question period needs readable meaning and sources')
    paths = value['paths']
    calendar = paths['calendar']
    if (not 2 <= len(calendar) <= 640 or calendar != sorted(set(calendar))
            or any(date.fromisoformat(d).isoformat() != d for d in calendar)
            or not calendar[0] < asked_on <= calendar[-1]
            or set(paths['stocks']) != {symbol} or paths['st_name'] != 'ST板块（东财）'):
        raise ValueError('question period must cover the original date with its own company')
    gaps = []
    for key, points in [('stock', paths['stocks'][symbol]['points']), ('market', paths['market']), ('st', paths['st'])]:
        if [p['date'] for p in points] != calendar:
            raise ValueError('question period series calendars differ')
        anchor = points[0]['value']
        if type(anchor) not in {int, float} or not Decimal(str(anchor)).is_finite() or anchor <= 0:
            raise ValueError('question observation needs an initial valid close')
        for point in points:
            price, level = point['value'], point['level']
            if price is None:
                if key != 'stock' or level is not None:
                    raise ValueError('only explicit stock quotes may be missing')
                gaps.append(point['date'])
            elif (type(price) not in {int, float} or type(level) not in {int, float}
                    or not Decimal(str(price)).is_finite() or not Decimal(str(level)).is_finite()
                    or min(price, level) <= 0
                    or abs(Decimal(str(level)) - Decimal(str(price))/Decimal(str(anchor))*100) > Decimal('.00000001')):
                raise ValueError('question price or normalization changed')
    closes = value['qfq_closes']
    if set(closes) != set(calendar)-set(gaps) or any(p['value'] != closes.get(p['date']) for p in paths['stocks'][symbol]['points']):
        raise ValueError('question chart differs from declared adjusted closes')
    start, end = calendar[0], calendar[-1]
    code = ('sh' if symbol.endswith('.SH') else 'sz') + symbol[:6]
    expected = {
        'tencent_qfq': 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + urlencode({'param': f'{code},day,{start},{end},640,qfq'}),
        'market': 'https://www.csindex.com.cn/csindex-home/perf/index-perf?' + urlencode({'indexCode': '000985', 'startDate': start.replace('-', ''), 'endDate': end.replace('-', '')}),
        'st': 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urlencode({'secid': '90.BK0511', 'klt': '101', 'fqt': '0', 'beg': start.replace('-', ''), 'end': end.replace('-', ''), 'fields1': 'f1,f2,f3,f4,f5,f6', 'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'}),
    }
    refs = value['source_refs']
    if len(refs) != len(expected) or {r['key'] for r in refs} != set(expected):
        raise ValueError('question period source inventory differs')
    for ref in refs:
        stamp = datetime.fromisoformat(ref['observed_at'])
        if (ref['url'] != expected[ref['key']] or not re.fullmatch(r'[a-f0-9]{64}', ref['sha256'])
                or stamp.tzinfo is None or stamp > datetime.now(timezone.utc)
                or stamp.date().isoformat() < end or not ref.get('title')):
            raise ValueError('question source identity or observation time changed')
    raw = next(r for r in refs if r['key'] == 'tencent_qfq')
    notes = value['gap_notes']
    if len(notes) != len(gaps) or sorted(n['date'] for n in notes) != gaps:
        raise ValueError('question gaps need explicit source notes')
    for note in notes:
        if (set(note) != {'date', 'reason', 'source_sha256', 'url'} or note['reason'] != GAP_NOTE
                or note['source_sha256'] != raw['sha256'] or note['url'] != raw['url']):
            raise ValueError('quote absence cannot claim a suspension cause')
    return paths
