"""Independently published CSI closes; never advance the ST/ETF comparison date."""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, sessions_2026
from market_public_refresh import CSIIndexClient, parse_index_perf
from market_risk import CSI_PERF_URL, INDEX_BASKET, MARKET_RISK_DIR

VERSION = 'independent_index_close_v1'
OUTPUT = MARKET_RISK_DIR / 'trader_observations/latest_index'
SHANGHAI = ZoneInfo('Asia/Shanghai')


def price_judgment(day, week, month):
    if month is not None and month < 0:
        headline = '大盘风险仍偏高，反弹尚未改变近月弱势' if day is not None and day > 0 else '大盘风险仍偏高，短期压力尚在'
        return headline, '弱势判断'
    if month is not None and week is not None and month > 0 and week > 0:
        return '短中期走势同向回升', '回升'
    if month is not None and month > 0:
        return '近月回升，短线仍有反复', '分化'
    return '方向仍不清晰，先看已有的价格变化', '待观察'


def _instant(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('undated index observation')
    return stamp


def _calendar(through, now):
    if now.tzinfo is None:
        raise ValueError('index publication needs a timezone')
    end = date.fromisoformat(through)
    # A price-only observation may publish after this buffer once the official
    # complete daily series exists. ETF T+1 revision and paired-source gates stay
    # in their own publishers, unchanged.
    floor = datetime.combine(end, time(15, 30), SHANGHAI)
    if now < floor:
        raise ValueError('index close is not yet eligible')
    calendar = sessions_2026(date(end.year, 1, 1), end)[-61:]
    if len(calendar) != 61 or calendar[-1] != through:
        raise ValueError('61 complete verified sessions required')
    return calendar, floor


def _verify(packet, directory, now):
    if (packet['version'] != VERSION or packet['calendar_version'] != CALENDAR_VERSION or packet['calendar_source'] != CALENDAR_SOURCE
        or packet['scope'] != 'three_price_indices_only' or packet['availability_basis'] != 'official_daily_close_first_observed_after_close'):
        raise ValueError('index publication version changed')
    expected = digest({k: v for k, v in packet.items() if k != 'content_digest'})
    if packet['content_digest'] != expected:
        raise ValueError('index publication changed')
    calendar, floor = _calendar(packet['through'], now)
    if packet['calendar'] != calendar or _instant(packet['checked_at']) > now:
        raise ValueError('index calendar or publication time changed')
    refs = packet['responses']
    if len(refs) != len(INDEX_BASKET) or {r['code'] for r in refs} != set(INDEX_BASKET) or set(packet['indices']) != set(INDEX_BASKET):
        raise ValueError('complete declared index identities required')
    for ref in refs:
        url = CSI_PERF_URL + '?' + urlencode({'indexCode': ref['code'][:6], 'startDate': calendar[0].replace('-', ''), 'endDate': calendar[-1].replace('-', '')})
        observed = _instant(ref['observed_at'])
        if (ref['url'] != url or observed < floor or observed > _instant(packet['checked_at'])
            or ref['reported_amount_unit'] != 'CNY100M' or ref['normalized_amount_unit'] != 'CNY'):
            raise ValueError('index source identity, units or observation time changed')
        key = ref['response_sha256']
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('invalid index original identity')
        raw = (directory / 'responses' / (key + '.json')).read_bytes()
        if sha256(raw).hexdigest() != ref['response_sha256']:
            raise ValueError('index original changed')
        rows = parse_index_perf(json.loads(raw), ref['code'], calendar)
        if [r['trade_date'] for r in rows] != calendar or rows != packet['indices'][ref['code']]:
            raise ValueError('incomplete index series or projection changed')
    return packet


def publish(client, *, through, directory=OUTPUT, now=None):
    calendar, _ = _calendar(through, now or datetime.now(timezone.utc))
    packet = {'version': VERSION, 'through': through, 'calendar': calendar,
              'calendar_version': CALENDAR_VERSION, 'calendar_source': CALENDAR_SOURCE,
              'availability_basis': 'official_daily_close_first_observed_after_close',
              'scope': 'three_price_indices_only', 'indices': {}, 'responses': []}
    for code in INDEX_BASKET:
        rows, ref = client.get_index(code, calendar)
        packet['indices'][code] = rows
        packet['responses'].append(ref)
    # Use actual completion time; test clients can supply a fixed publication time.
    checked = now or datetime.now(timezone.utc)
    packet['checked_at'] = checked.isoformat()
    packet['content_digest'] = digest(packet)
    _verify(packet, directory, checked)
    atomic_write_json(directory / 'snapshots' / (packet['content_digest'] + '.json'), packet)
    atomic_write_json(directory / 'current.json', packet)
    return packet


def newer_price(base, *, directory=OUTPUT, now=None):
    """Called at explicit/background publication, never fetches from a request."""
    try:
        packet = _verify(json.loads((directory / 'current.json').read_text()), directory, now or datetime.now(timezone.utc))
        if packet['through'] <= base['as_of']:
            return None
        points = packet['indices']['000985.CSI']
        by_day = {p['trade_date']: p['close'] for p in points}
        common = next(line['points'] for line in base['chart'] if line['key'] == 'market')
        # A new quote cannot silently rewrite the history paired with ST.
        if not common or any(p['date'] not in by_day or Decimal(str(p['value'])) != Decimal(str(by_day[p['date']])) for p in common):
            return None
        def change(n):
            return float((Decimal(str(points[-1]['close'])) / Decimal(str(points[-n-1]['close'])) - 1) * 100)
        day, week, month = change(1), change(5), change(20)
        headline, stance = price_judgment(day, week, month)
        source = next(r for r in packet['responses'] if r['code'] == '000985.CSI')['url']
        text = f"{packet['through']}中证全指{day:+.2f}%；最近5个交易日{week:+.2f}%，最近20个交易日{month:+.2f}%。"
        return {'availability': 'available', 'as_of': packet['through'], 'headline': headline, 'stance': stance,
                'summary': text, 'metrics': {'day_change_pct': day, 'five_day_change_pct': week, 'twenty_day_change_pct': month},
                'reason': {'title': '先看最新的价格方向', 'text': text, 'source_label': '中证全指原始收盘来源', 'source_url': source},
                'source_digest': packet['content_digest'], 'checked_at': packet['checked_at']}
    except (OSError, ValueError, KeyError, TypeError, StopIteration, IndexError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--through', required=True)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    packet = publish(CSIIndexClient(args.output / 'responses'), through=args.through, directory=args.output)
    print(json.dumps({'through': packet['through'], 'source_digest': packet['content_digest'], 'scope': packet['scope']}))


if __name__ == '__main__':
    main()
