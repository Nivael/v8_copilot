"""Recover selected-company limits from saved provider responses, not a live feed."""
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
import gzip
import json
from market_calendar import sessions_2026
from datetime import date

WATCHED = {'603398.SH','600363.SH','002667.SZ','688053.SH','002514.SZ'}
FIELDS = ['trade_date','ts_code','pre_close','up_limit','down_limit']


def replay(evidence, folder):
    folder = Path(folder)
    days = sessions_2026(date(2026,11,9), date(2026,11,19))
    refs = evidence['sources']
    if sorted(r['date'] for r in refs) != days:
        raise ValueError('nine saved limit sessions required')
    selected = {}
    counts = {}
    for ref in refs:
        raw = gzip.decompress((folder/(ref['response_sha256']+'.json.gz')).read_bytes())
        if len(raw) != ref['bytes'] or sha256(raw).hexdigest() != ref['response_sha256']:
            raise ValueError('original limit response bytes changed')
        day = ref['date']; compact = day.replace('-','')
        if ref['api_name'] != 'stk_limit' or ref['params'] != {'trade_date':compact} or ref['fields'].split(',') != FIELDS:
            raise ValueError('limit request identity changed')
        data = json.loads(raw)
        if data['code'] != 0 or data['data']['fields'] != FIELDS:
            raise ValueError('limit response failed or fields changed')
        items=data['data']['items'];counts[day]=len(items)
        if len(items)>=6000:
            raise ValueError('saved provider row cap reached')
        seen=set()
        for item in items:
            row=dict(zip(FIELDS,item,strict=True))
            if row['trade_date'] != compact or row['ts_code'] in seen:
                raise ValueError('limit date or duplicate security changed')
            seen.add(row['ts_code'])
            if row['ts_code'] not in WATCHED:continue
            vals=[D(str(row[k])) for k in ('pre_close','up_limit','down_limit')]
            if any(not v.is_finite() or v<=0 for v in vals) or not vals[2]<=vals[0]<=vals[1]:
                raise ValueError('invalid selected limit prices')
            selected[(row['ts_code'][:6],day)]={k:str(row[k]) for k in ('pre_close','up_limit','down_limit')}
        if not WATCHED<=seen:raise ValueError('selected limit security missing')
    bars=evidence['ohlc_reading'];rows=[]
    for company in bars['companies']:
        for bar in company['days']:
            key=(company['symbol'],bar['date']);limits=selected[key]
            down,up=D(limits['down_limit']),D(limits['up_limit'])
            prices={k:D(bar[k]) for k in ('open','close','high','low')}
            if prices['low']<down or prices['high']>up:
                raise ValueError('OHLC outside saved actual limits')
            rows.append({'symbol':key[0],'date':key[1],**limits,
                         'close':bar['close'],'low':bar['low'],'high':bar['high'],
                         'close_at_down_limit':prices['close']==down,
                         'low_at_down_limit':prices['low']==down,
                         'one_price_at_down_limit':all(v==down for v in prices.values())})
    if len(rows)!=44 or len({(r['symbol'],r['date']) for r in rows})!=44:
        raise ValueError('frozen 44-trading-day OHLC scope changed')
    unused=sorted(set(selected)-{(r['symbol'],r['date'])for r in rows})
    return {'version':'recovered_selected_limits_v1','start':days[0],'through':days[-1],
            'limit_records':len(selected),'trading_ohlc_pairs':len(rows),
            'without_trading_ohlc':[{'symbol':s,'date':d}for s,d in unused],
            'close_at_down_limit_days':sum(r['close_at_down_limit']for r in rows),
            'touch_down_limit_days':sum(r['low_at_down_limit']for r in rows),
            'one_price_at_down_limit_days':sum(r['one_price_at_down_limit']for r in rows),
            'response_rows_by_day':counts,'rows':rows,
            'scope':'此前五家公司，含科创板且期间摘帽的思科瑞；不代表同期主板ST或全市场。',
            'boundary':'主库缺近期数据不等于所有留档都缺。这里只复用九日供应商限价原件；不是交易所独立限价确认，不提供历史队列、可成交量、实际委托或退出成本，也不延伸到11月20日。'}
