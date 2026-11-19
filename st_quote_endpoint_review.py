"""Review actual-trade endpoints without hiding missing data or basis conflicts."""
from decimal import Decimal
from hashlib import sha256
import json


def review_stock_endpoints(sources, prices, codes, dates):
    if len(set(codes)) != len(codes) or len(set(dates)) != len(dates):
        raise ValueError('duplicate review scope')
    expected = {'sz' + c for c in codes}
    if len(sources) != len(expected) or {s['key'] for s in sources} != expected:
        raise ValueError('quote source scope changed')
    lookup = {}
    for row in prices:
        key = row['symbol'], row['trade_date']
        if key in lookup:
            raise ValueError('duplicate provider date')
        lookup[key] = row
    results = []
    for source in sources:
        key = source['key']
        code = key[2:]
        if sha256(source['text'].encode()).hexdigest() != source['sha256']:
            raise ValueError('quote bytes changed')
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={key},day,{dates[0]},{dates[-1]},320,qfq'
        if source['url'] != url:
            raise ValueError('quote request changed')
        block = json.loads(source['text'])['data'][key]
        if block['qt'][key][2] != code:
            raise ValueError('quote identity changed')
        raw = block.get('qfqday') or block.get('day') or []
        quotes = {r[0]: r for r in raw}
        if len(quotes) != len(raw) or any(r[0] > dates[-1] for r in raw):
            raise ValueError('duplicate or future quote')
        points = []
        for day in dates:
            provider = lookup.get((code, day))
            cross = quotes.get(day)
            pa = bool(provider and provider['has_trade'] and provider.get('close') is not None)
            ca = bool(cross and Decimal(cross[5]) > 0)
            if not pa and not ca:
                status = 'no_actual_trade_endpoint'
            elif pa != ca:
                status = 'availability_conflict'
            else:
                a, b = Decimal(str(provider['close'])), Decimal(cross[2])
                if not a.is_finite() or not b.is_finite() or min(a, b) <= 0:
                    raise ValueError('invalid actual price')
                status = 'matched' if abs(a - b) <= Decimal('0.000000001') else 'price_basis_conflict'
            points.append({'date': day, 'status': status,
                           'provider_close': provider.get('close') if provider else None,
                           'cross_close': cross[2] if cross else None,
                           'provider_has_trade': pa, 'cross_has_trade': ca})
        windows = []
        for end in points[1:]:
            usable = all(r['status'] == 'matched' for r in (points[0], end))
            value = float((Decimal(end['cross_close']) / Decimal(points[0]['cross_close']) - 1) * 100) if usable else None
            windows.append({'anchor': dates[0], 'through': end['date'],
                            'return_pct': value,
                            'gaps': [r for r in (points[0], end) if r['status'] != 'matched']})
        results.append({'symbol': code, 'points': points, 'windows': windows,
                        'source_sha256': source['sha256']})
    return results
