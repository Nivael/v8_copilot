"""Source-bound additions to an immutable historical-price base."""
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from canonical_json import digest

SOURCE_VERSION = 'research_subject_qfq_source_v1'
EXTENSION_VERSION = 'research_subject_paths_v1'


def processor_digest():
    return sha256(Path(__file__).read_bytes()).hexdigest()


def cash_dividend(row):
    """Only the documented cash-event shape; preserve the original row bytes."""
    if len(row) == 6:
        return None
    if len(row) != 7 or not isinstance(row[6], dict):
        raise ValueError('unsupported subject quote columns')
    meta = row[6]
    if set(meta) != {'nd', 'fh_sh', 'djr', 'cqr', 'FHcontent'}:
        raise ValueError('unsupported subject corporate-action fields')
    if any(not isinstance(v, str) for v in meta.values()):
        raise ValueError('corporate-action values must retain original strings')
    day = date.fromisoformat(row[0])
    year = meta['nd']
    content = re.fullmatch(r'10派(\d+(?:\.\d+)?)元', meta['FHcontent'])
    amount = Decimal(meta['fh_sh'])
    if (not re.fullmatch(r'20\d{2}', year) or int(year) > day.year
            or date.fromisoformat(meta['cqr']) != day or date.fromisoformat(meta['djr']) >= day
            or not amount.is_finite() or amount < 0 or not content
            or Decimal(content[1]) != amount):
        raise ValueError('corporate-action date or cash amount changed')
    return dict(meta)


def supplemental_subject_history(root, symbol, calendar, historical, official):
    """Read a new subject's complete qfq window, including explicit cash metadata."""
    from research_history_prices import bound
    if not re.fullmatch(r'(?:[03]\d{5}\.SZ|6\d{5}\.SH)', symbol):
        raise ValueError('unsupported subject security identity')
    folder = root / 'inputs/subject_qfq_v1'
    ref = bound(folder / (symbol[:6] + '.json'))
    code = symbol[:6]
    key = ('sh' if symbol.endswith('.SH') else 'sz') + code
    end = date.fromisoformat(ref['through']).isoformat()
    expected = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + urlencode({'param': f'{key},day,{calendar[0]},{end},640,qfq'})
    raw = (folder / (ref['sha256'] + '.json')).read_bytes()
    observed = datetime.fromisoformat(ref['observed_at'])
    if (ref['version'] != SOURCE_VERSION or ref['url'] != expected or ref['response_url'] != expected
            or sha256(raw).hexdigest() != ref['sha256'] or len(raw) != ref['bytes']
            or observed.tzinfo is None or observed > datetime.now(timezone.utc)
            or end > calendar[-1] or end < '2026-09-03'
            or end > observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()):
        raise ValueError('subject source identity or time changed')
    value = json.loads(raw)
    data = value.get('data', {}).get(key, {})
    quote = data.get('qt', {}).get(key, [])
    if value.get('code') != 0 or len(quote) < 3 or quote[2] != code or not quote[1]:
        raise ValueError('subject stock identity changed')
    result = {}; events = []; previous = ''; valid = set(calendar)
    for row in data.get('qfqday', []):
        event = cash_dividend(row)
        if any(not isinstance(v, str) for v in row[:6]):
            raise ValueError('subject quote decimals must retain source strings')
        day = date.fromisoformat(row[0]).isoformat()
        values = [Decimal(v) for v in row[1:6]]
        op, close, high, low, volume = values
        if (day <= previous or day not in valid or day > end or any(not v.is_finite() for v in values)
                or min(op, close, low) <= 0 or high < max(op, close, low)
                or low > min(op, close) or volume <= 0):
            raise ValueError('subject quote dates or prices changed')
        result[day] = {'close': float(close), 'volume': float(volume)}
        previous = day
        if event:
            events.append({'date': day, 'original_metadata': event})
    endpoint = official.get(end)
    if (not result or next(iter(result)) != calendar[0] or previous != end or '2026-09-03' not in result
            or not endpoint or not endpoint['is_trading'] or abs(result[end]['close'] - endpoint['close']) > .011):
        raise ValueError('subject endpoint or hand-off is unverified')
    checked = 0; previous_close = None
    for day, row in result.items():
        point = official.get(day)
        if day >= '2026-09-04' and previous_close and point and point['is_trading']:
            if (min(point['close'], point['previous_close']) <= 0
                    or abs(row['close'] / previous_close - point['close'] / point['previous_close']) > .0008):
                raise ValueError('subject return differs from official source')
            checked += 1
        previous_close = row['close']
    if checked < 20 or ref.get('historical_basis_replaced') is not True or not ref.get('basis_review_note'):
        raise ValueError('subject replacement needs twenty official comparisons and an explicit review')
    selected = {**{d: r for d, r in historical.items() if d >= '2026-09-04'},
                **{d: r for d, r in result.items() if d < '2026-09-04'}}
    return selected, ref, {'official_return_checks': checked, 'cash_events': events, 'source_rows': len(result)}


def extension_packet(base, data, *, root=None):
    added = sorted(set(data['stocks']) - set(base['data']['stocks']))
    extra_sources = {k: v for k, v in data['source_digests'].items() if k not in base['data']['source_digests']}
    stamp = datetime.now(timezone.utc).isoformat()
    extension = {'version': EXTENSION_VERSION, 'processor_digest': processor_digest(),
                 'base_price_digest': base['content_digest'], 'added_symbols': added,
                 'added_paths_digest': digest({k: data['stocks'][k] for k in added}),
                 'added_sources_digest': digest(extra_sources), 'created_at': stamp}
    extension['content_digest'] = digest(extension)
    packet = {'version': base['version'], 'processor_digest': base['processor_digest'],
              'checked_at': stamp, 'data': data, 'subject_extension': extension}
    packet['content_digest'] = digest(packet)
    validate_extension(packet, base=base, root=root)
    return packet


def validate_extension(packet, *, root=None, base=None, seen=None):
    """Old paths and shared benchmarks stay exact; code changes require reprocessing."""
    from research_history_prices import bound
    extension = packet.get('subject_extension')
    if extension is None:
        return
    seen = set() if seen is None else set(seen)
    key = extension['base_price_digest']
    if not re.fullmatch(r'[a-f0-9]{64}', key) or key in seen or len(seen) >= 32:
        raise ValueError('invalid historical-price base chain')
    seen.add(key)
    if base is None:
        if root is None:
            raise ValueError('historical-price base is required')
        base = bound(root / 'price_paths/history' / (key + '.json'))
    validate_extension(base, root=root, seen=seen)
    data = packet['data']; old = base['data']; added = extension['added_symbols']
    stamp = datetime.fromisoformat(extension['created_at'])
    if (extension['version'] != EXTENSION_VERSION or extension['processor_digest'] != processor_digest()
            or digest({k: v for k, v in extension.items() if k != 'content_digest'}) != extension['content_digest']
            or key != base['content_digest'] or packet['processor_digest'] != base['processor_digest']
            or stamp.tzinfo is None or stamp > datetime.now(timezone.utc)
            or not added or added != sorted(set(added))
            or set(data['stocks']) != set(old['stocks']) | set(added) or set(added) & set(old['stocks'])
            or any(not re.fullmatch(r'(?:[03]\d{5}\.SZ|6\d{5}\.SH)', code) for code in added)
            or any(data['stocks'][code] != stock for code, stock in old['stocks'].items())
            or {k: v for k, v in data.items() if k not in {'stocks', 'source_digests'}} != {k: v for k, v in old.items() if k not in {'stocks', 'source_digests'}}
            or any(data['source_digests'].get(k) != v for k, v in old['source_digests'].items())
            or digest({k: data['stocks'][k] for k in added}) != extension['added_paths_digest']
            or digest({k: v for k, v in data['source_digests'].items() if k not in old['source_digests']}) != extension['added_sources_digest']):
        raise ValueError('historical-price extension changed its base or processing')
    for code in added:
        stock = data['stocks'][code]
        if stock['as_of'] != data['calendar'][-1] or [p['date'] for p in stock['points']] != data['calendar']:
            raise ValueError('added subject calendar changed')
        for point in stock['points']:
            value, level = point['value'], point['level']
            if (point['basis'] not in {'historical_qfq', 'historical_gap', 'official_previous_close', 'missing', 'not_trading'}
                    or any(v is not None and (type(v) not in (int, float) or not isfinite(v) or v <= 0) for v in (value, level))
                    or value is None and level is not None):
                raise ValueError('invalid added subject price or gap')
