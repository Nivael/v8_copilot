"""Describe saved daily candles; never infer queue liquidity or limit prices."""
from decimal import Decimal as D
from hashlib import sha256
import json

def observe(sources, primary, start='2026-11-09', through='2026-11-19'):
    expected={k.split('.')[0]:{r['date']:r for r in v if start<=r['date']<=through} for k,v in primary.items()}
    result=[];seen=set()
    for s in sources:
        if not s['key'].endswith('-raw'):continue
        ticker=s['key'].split('-')[0];symbol=ticker[2:]
        if symbol in seen or symbol not in expected:raise ValueError('duplicate or unscoped source')
        seen.add(symbol)
        if sha256(s['text'].encode()).hexdigest()!=s['sha256']:raise ValueError('source bytes changed')
        b=json.loads(s['text'])['data'][ticker]
        if b['qt'][ticker][2]!=symbol:raise ValueError('source identity changed')
        rows=[];dates=[]
        for r in b['day']:
            day=r[0];dates.append(day)
            if not start<=day<=through:continue
            if len(r)!=6:raise ValueError('daily columns changed')
            op,cl,hi,lo,vol=map(D,r[1:])
            if any(not v.is_finite()or v<=0 for v in (op,cl,hi,lo,vol))or not lo<=min(op,cl)<=max(op,cl)<=hi:raise ValueError('invalid daily candle')
            p=expected[symbol].get(day)
            if p is None or cl!=D(str(p['raw_close']))or D(str(p['volume']))<=0:raise ValueError('primary close/activity mismatch')
            rows.append({'date':day,'open':str(op),'close':str(cl),'high':str(hi),'low':str(lo),'source_volume_native_units':str(vol),'one_observed_price':op==cl==hi==lo,'close_at_low':cl==lo,'intraday_range_yuan':str(hi-lo)})
        if dates!=sorted(set(dates)):raise ValueError('duplicate/unsorted dates')
        if {r['date']for r in rows}!={d for d,p in expected[symbol].items()if D(str(p['volume']))>0}:raise ValueError('trading date mismatch')
        result.append({'symbol':symbol,'observed_trading_days':len(rows),'one_price_days':sum(r['one_observed_price']for r in rows),'close_at_low_days':sum(r['close_at_low']for r in rows),'days':rows,'source':{k:s[k]for k in ('key','url','sha256','observed_at')}})
    if seen!=set(expected):raise ValueError('missing scoped security')
    return {'version':'st_exit_daily_observation_v1','start':start,'through':through,'companies':result,'total_trading_stock_days':sum(r['observed_trading_days']for r in result),'one_price_stock_days':sum(r['one_price_days']for r in result),'close_at_low_stock_days':sum(r['close_at_low_days']for r in result),'actual_limit_price_available':False,'queue_data_available':False,'executable_exit_verified':False}
