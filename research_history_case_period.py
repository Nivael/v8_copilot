"""A separate, source-bound past case window; never a replacement question anchor."""
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode
import re
from canonical_json import digest

VERSION = 'history_case_period_sources_v1'


def case_period_paths(value, *, symbol, asked_on, current_start):
    if (not isinstance(value, dict) or value.get('version') != VERSION
            or value.get('price_basis') != 'unadjusted_price'
            or value.get('symbol') != symbol
            or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value.get('content_digest')):
        raise ValueError('case period source binding changed')
    if not re.fullmatch(r'(?:[03]\d{5}\.SZ|6\d{5}\.SH)', symbol):
        raise ValueError('unsupported case security')
    for key in ['title', 'summary', 'source_note']:
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError('case period needs its readable meaning and source note')
    paths = value['paths']
    calendar = paths['calendar']
    if (not 2 <= len(calendar) <= 750 or calendar != sorted(set(calendar))
            or any(date.fromisoformat(d).isoformat() != d for d in calendar)
            or calendar[-1] >= min(asked_on, current_start)
            or set(paths['stocks']) != {symbol}
            or paths['st_name'] != 'ST板块（东财）'):
        raise ValueError('case period must precede, and remain separate from, the question window')
    gaps = []
    for key, points in [('stock', paths['stocks'][symbol]['points']),
                        ('market', paths['market']), ('st', paths['st'])]:
        if [p['date'] for p in points] != calendar:
            raise ValueError('case series calendars differ')
        anchor = points[0]['value']
        if type(anchor) not in {int, float} or not Decimal(str(anchor)).is_finite() or anchor <= 0:
            raise ValueError('case observation start needs a valid close')
        for point in points:
            price, level = point['value'], point['level']
            if price is None:
                if level is not None or key != 'stock':
                    raise ValueError('only an explicit stock gap may be missing')
                gaps.append(point['date'])
                continue
            if (type(price) not in {int, float} or type(level) not in {int, float}
                    or not Decimal(str(price)).is_finite() or not Decimal(str(level)).is_finite()
                    or min(price, level) <= 0
                    or abs(Decimal(str(level)) - Decimal(str(price))/Decimal(str(anchor))*100) > Decimal('.00000001')):
                raise ValueError('case price or normalization changed')
    notes = value['gap_notes']
    if len(notes) != len(gaps) or sorted(n['date'] for n in notes) != gaps:
        raise ValueError('case gaps need one explicit primary note each')
    for note in notes:
        if (not isinstance(note.get('reason'), str) or not note['reason'].strip()
                or not re.fullmatch(r'\d{10}', note['announcement_id'])
                or not re.fullmatch(r'https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/'
                                    + note['announcement_id'] + r'\.PDF#page=[1-9]\d*', note['url'])):
            raise ValueError('case gap primary identity changed')
    raw = value['unadjusted_closes']
    if set(raw) != set(calendar)-set(gaps) or any(type(v) not in {int, float} or
            not Decimal(str(v)).is_finite() or v <= 0 for v in raw.values()):
        raise ValueError('unadjusted quotes differ from the trading scope')
    if any(p['value'] != raw.get(p['date']) for p in paths['stocks'][symbol]['points']):
        raise ValueError('case chart must use the declared unadjusted closes')
    start, end = calendar[0], calendar[-1]
    code = ('sh' if symbol.endswith('.SH') else 'sz') + symbol[:6]
    expected = {
        'tencent_qfq': 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + urlencode({'param': f'{code},day,{start},{end},640,qfq'}),
        'tencent_unadjusted': 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + urlencode({'param': f'{code},day,{start},{end},640,'}),
        'market': 'https://www.csindex.com.cn/csindex-home/perf/index-perf?' + urlencode({'indexCode': '000985', 'startDate': start.replace('-', ''), 'endDate': end.replace('-', '')}),
    }
    common = {'klt': '101', 'beg': start.replace('-', ''), 'end': end.replace('-', ''),
              'fields1': 'f1,f2,f3,f4,f5,f6', 'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'}
    for key, secid, fqt in [('st', '90.BK0511', '0'),
                            ('eastmoney_qfq', ('1.' if symbol.endswith('.SH') else '0.') + symbol[:6], '1')]:
        expected[key] = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urlencode({
            'secid': secid, 'klt': common['klt'], 'fqt': fqt, **{k: v for k, v in common.items() if k != 'klt'}})
    refs = value['source_refs']
    if len(refs) != len(expected) or {r['key'] for r in refs} != set(expected):
        raise ValueError('case source inventory differs')
    for ref in refs:
        stamp = datetime.fromisoformat(ref['observed_at'])
        if (ref['url'] != expected[ref['key']] or not re.fullmatch(r'[a-f0-9]{64}', ref['sha256'])
                or stamp.tzinfo is None or stamp > datetime.now(timezone.utc) or stamp.date().isoformat() < end
                or not ref.get('title')):
            raise ValueError('case source identity or observation time changed')
    return paths
