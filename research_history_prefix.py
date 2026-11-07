"""Prepend verified earlier sessions without rewriting an assessed price window."""
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from canonical_json import digest
from market_calendar import sessions_2026

SOURCE_VERSION = 'research_history_prefix_sources_v1'
VERSION = 'research_history_calendar_prefix_v1'


def processor_digest():
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _bound(value):
    if digest({k: v for k, v in value.items() if k != 'content_digest'}) != value['content_digest']:
        raise ValueError('earlier-price binding changed')
    return value


def _raw(folder, ref, expected_url=None):
    key = ref['sha256']
    if not re.fullmatch(r'[a-f0-9]{64}', key):
        raise ValueError('invalid earlier-price source identity')
    raw = (folder / (key + '.json')).read_bytes()
    stamp = datetime.fromisoformat(ref['observed_at'])
    if (sha256(raw).hexdigest() != key or len(raw) != ref['bytes'] or stamp.tzinfo is None
            or stamp > datetime.now(timezone.utc)
            or expected_url is not None and (ref['url'] != expected_url or ref['response_url'] != expected_url)):
        raise ValueError('earlier-price original or observation changed')
    return json.loads(raw), stamp


def _number(value, *, positive=False):
    result = Decimal(str(value))
    if not result.is_finite() or positive and result <= 0:
        raise ValueError('invalid earlier-price number')
    return result


def _days(rows, calendar):
    if list(rows) != calendar:
        raise ValueError('earlier-price calendar is incomplete or unordered')


def prefix_data(base, source, folder):
    """Derive prices from raw sources, with a second stock source and an exact join."""
    _bound(source)
    old = base['data']
    first, end = old['calendar'][0], old['calendar'][-1]
    start = date.fromisoformat(source['start']).isoformat()
    calendar = sessions_2026(date.fromisoformat(start), date.fromisoformat(first))
    symbols = source['symbols']
    if (source['version'] != SOURCE_VERSION or source['join'] != first or source['through'] != end
            or start >= first or symbols != sorted(set(symbols)) or not symbols
            or any(not re.fullmatch(r'[03]\d{5}\.SZ', code) or code not in old['stocks'] for code in symbols)
            or set(source['sources']) != {'market', 'st', 'local_qfq', *symbols}):
        raise ValueError('earlier-price source scope changed')
    result = deepcopy(old)
    result['calendar'] = calendar[:-1] + old['calendar']
    refs = source['sources']
    market_url = 'https://www.csindex.com.cn/csindex-home/perf/index-perf?' + urlencode({
        'indexCode': '000985', 'startDate': start.replace('-', ''), 'endDate': first.replace('-', '')})
    value, stamp = _raw(folder, refs['market'], market_url)
    if str(value['code']) != '200' or first > stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():
        raise ValueError('earlier market source is not available')
    market = {}; previous = None
    for row in value['data']:
        day = datetime.strptime(row['tradeDate'], '%Y%m%d').date().isoformat()
        close = _number(row['close'], positive=True)
        if row['indexCode'] != '000985' or day in market:
            raise ValueError('earlier market identity changed')
        if previous is not None and abs((close / previous - 1) * 100 - _number(row['changePct'])) > Decimal('.015'):
            raise ValueError('earlier market return differs from its reported change')
        market[day] = close
        previous = close
    _days(market, calendar)
    st_url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urlencode({
        'secid': '90.BK0511', 'klt': '101', 'fqt': '0', 'beg': start.replace('-', ''),
        'end': first.replace('-', ''), 'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'})
    value, stamp = _raw(folder, refs['st'], st_url)
    if (value['rc'] != 0 or value['data']['code'] != 'BK0511' or value['data']['name'] != 'ST股'
            or old['st_name'] != 'ST板块（东财）'
            or old['st_source_url'] != 'https://quote.eastmoney.com/bk/90.BK0511.html'
            or first > stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()):
        raise ValueError('earlier ST series identity changed')
    st = {}; previous = None
    for raw_row in value['data']['klines']:
        row = raw_row.split(',')
        if len(row) != 11:
            raise ValueError('earlier ST columns changed')
        day = date.fromisoformat(row[0]).isoformat()
        values = [_number(v) for v in row[1:]]
        close = _number(row[2], positive=True)
        if day in st or min(values[4:6]) < 0:
            raise ValueError('earlier ST date or volume changed')
        if previous is not None and abs((close / previous - 1) * 100 - values[7]) > Decimal('.015'):
            raise ValueError('earlier ST return differs from its reported change')
        st[day] = close
        previous = close
    _days(st, calendar)
    for key, rows in [('market', market), ('st', st)]:
        join = old[key][0]
        if join['date'] != first or rows[first] != _number(join['value'], positive=True):
            raise ValueError('earlier benchmark join differs from retained price')
        level = _number(join['level'], positive=True)
        result[key] = [{'date': d, 'value': float(rows[d]), 'level': float(rows[d] / rows[first] * level)}
                       for d in calendar[:-1]] + old[key]
    sql, sql_stamp = _raw(folder, refs['local_qfq'])
    _bound(sql)
    codes = ','.join("'" + s[:6] + "'" for s in symbols)
    expected_query = ("select symbol,trade_date,close,volume,pct_change,source from daily_prices "
                      "where adjust='qfq' and symbol in (" + codes + ") and trade_date between '" + start
                      + "' and '" + first + "' order by symbol,trade_date")
    if (sql['version'] != 'research_history_sql_selection_v1' or sql['query'] != expected_query
            or not sql['source_file'].endswith('.sqlite3') or sql['observed_at'] != refs['local_qfq']['observed_at']
            or first > sql_stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()):
        raise ValueError('earlier local quote selection changed')
    local = {code: {} for code in symbols}
    for row in sql['rows']:
        code = row['symbol'] + '.SZ'
        if code not in local or row['trade_date'] in local[code] or row['source'] != 'tushare:daily+adj_factor:qfq':
            raise ValueError('earlier local quote identity changed')
        local[code][row['trade_date']] = row
    for code in symbols:
        _days(local[code], calendar)
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + urlencode({
            'param': f'sz{code[:6]},day,{start},{end},640,qfq'})
        value, stamp = _raw(folder, refs[code], url)
        key = 'sz' + code[:6]
        body = value.get('data', {}).get(key, {})
        quote = body.get('qt', {}).get(key, [])
        if (value.get('code') != 0 or len(quote) < 3 or quote[2] != code[:6] or not quote[1]
                or end > stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()):
            raise ValueError('earlier stock identity or availability changed')
        rows = {}; previous = ''
        valid = set(result['calendar'])
        for row in body.get('qfqday', []):
            if len(row) != 6 or any(not isinstance(v, str) for v in row):
                raise ValueError('earlier stock columns or adjustment metadata need a separate review')
            day = date.fromisoformat(row[0]).isoformat()
            op, close, high, low, volume = [_number(v, positive=True) for v in row[1:]]
            if day <= previous or day not in valid or high < max(op, close, low) or low > min(op, close):
                raise ValueError('earlier stock dates or OHLC changed')
            rows[day] = (close, volume)
            previous = day
        if not rows or next(iter(rows)) != start or previous != end:
            raise ValueError('earlier stock endpoints are incomplete')
        for day in calendar:
            row = local[code][day]
            # Tencent displays whole lots; the local daily source retains fractional lots.
            if (day not in rows or rows[day][0] != _number(row['close'], positive=True)
                    or rows[day][1] != _number(row['volume'], positive=True).quantize(Decimal('1'), rounding=ROUND_HALF_UP)):
                raise ValueError('earlier stock sources disagree')
        stock = old['stocks'][code]
        join = stock['points'][0]
        if join['date'] != first or rows[first][0] != _number(join['value'], positive=True):
            raise ValueError('earlier stock join differs from retained quote')
        checks = 0; previous = None
        for point in stock['points']:
            if point['value'] is None or point['level'] is None:
                continue
            day = point['date']
            if day not in rows or abs(rows[day][0] - _number(point['value'], positive=True)) > Decimal('.011'):
                raise ValueError('earlier stock adjustment differs across retained overlap')
            level = _number(point['level'], positive=True)
            if previous is not None:
                old_level, old_close = previous
                if abs(level / old_level - rows[day][0] / old_close) > Decimal('.0008'):
                    raise ValueError('earlier stock return differs across retained overlap')
                checks += 1
            previous = level, rows[day][0]
        if checks < 20:
            raise ValueError('earlier stock needs twenty retained overlap returns')
        stock_level = _number(join['level'], positive=True)
        result['stocks'][code]['points'] = [
            {'date': d, 'value': float(rows[d][0]), 'level': float(rows[d][0] / rows[first][0] * stock_level),
             'basis': 'historical_qfq'} for d in calendar[:-1]] + stock['points']
        result['stocks'][code]['earlier_history_source_url'] = url
        result['stocks'][code]['earlier_history_note'] = (
            f'{start}至{calendar[-2]}补入前复权日线，与另存的本地历史行情逐日交叉核对，'
            f'并核对与{first}以后原路径的重叠价格及收益；原有日期的价格点保持不变。')
    for code in set(old['stocks']) - set(symbols):
        result['stocks'][code]['points'] = [
            {'date': d, 'value': None, 'level': None, 'basis': 'missing'} for d in calendar[:-1]] + old['stocks'][code]['points']
    if 'independent_st' in old:
        result['independent_st'] = [{'date': d, 'value': None, 'level': None, 'coverage_ratio': 0,
                                     'daily_return_pct': None} for d in calendar[:-1]] + old['independent_st']
    result['source_digests']['calendar_prefix_' + source['content_digest'][:16]] = source['content_digest']
    return result


def extension_packet(base, source_digest, *, root):
    from research_history_prices import bound
    validate_price_packet(base, root=root)
    folder = root / 'inputs/calendar_prefix_v1'
    source = bound(folder / (source_digest + '.json'))
    data = prefix_data(base, source, folder)
    stamp = datetime.now(timezone.utc).isoformat()
    extension = {'version': VERSION, 'processor_digest': processor_digest(), 'base_price_digest': base['content_digest'],
                 'source_digest': source_digest, 'created_at': stamp}
    extension['content_digest'] = digest(extension)
    packet = {'version': base['version'], 'processor_digest': base['processor_digest'], 'checked_at': stamp,
              'data': data, 'calendar_extension': extension}
    packet['content_digest'] = digest(packet)
    validate_price_packet(packet, root=root, base=base)
    return packet


def validate_price_packet(packet, *, root=None, base=None, seen=None):
    """Validate either extension kind and every retained ancestor, including mixed chains."""
    from research_history_prices import bound
    from research_history_subjects import validate_extension
    extension = packet.get('calendar_extension')
    subject = packet.get('subject_extension')
    if extension is None and subject is None:
        return
    if extension is not None and subject is not None:
        raise ValueError('price extension kinds cannot be mixed in one packet')
    entry = extension or subject
    key = entry['base_price_digest']
    seen = set() if seen is None else set(seen)
    if not re.fullmatch(r'[a-f0-9]{64}', key) or key in seen or len(seen) >= 32:
        raise ValueError('invalid historical-price base chain')
    seen.add(key)
    if base is None:
        if root is None:
            raise ValueError('historical-price base is required')
        base = bound(root / 'price_paths/history' / (key + '.json'))
    validate_price_packet(base, root=root, seen=seen)
    if extension is None:
        validate_extension(packet, root=root, base=base)
        return
    _bound(packet); _bound(extension)
    stamp = datetime.fromisoformat(extension['created_at'])
    source_key = extension['source_digest']
    if (extension['version'] != VERSION or extension['processor_digest'] != processor_digest()
            or key != base['content_digest'] or packet['processor_digest'] != base['processor_digest']
            or packet['version'] != base['version'] or packet['checked_at'] != extension['created_at']
            or stamp.tzinfo is None or stamp > datetime.now(timezone.utc)
            or not re.fullmatch(r'[a-f0-9]{64}', source_key) or root is None):
        raise ValueError('historical-price calendar extension changed its base or processing')
    folder = root / 'inputs/calendar_prefix_v1'
    source = bound(folder / (source_key + '.json'))
    if source['content_digest'] != source_key or packet['data'] != prefix_data(base, source, folder):
        raise ValueError('historical-price calendar extension differs from verified sources or retained data')
