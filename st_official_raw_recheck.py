"""Replay frozen exchange originals against the explicitly scoped saved prices."""
from decimal import Decimal as D
from hashlib import sha256
import json

def replay(e):
    counts=[]
    for item in e['inputs']:
        raw=item['official_raw_text'];ref=item['official_source'];code=item['symbol']
        if sha256(raw.encode()).hexdigest()!=ref['sha256'] or len(raw.encode())!=ref['bytes']:raise ValueError('official bytes changed')
        p=json.loads(raw,parse_float=D)
        if p['code']!=code or ref['code']!=code or ref['url']!='https://yunhq.sse.com.cn:32042/v1/sh1/dayk/'+code:raise ValueError('official identity changed')
        if p['end']!=p['total'] or p['begin']!=max(0,p['total']+ref['params']['begin']+1) or len(p['kline'])!=p['end']-p['begin']:raise ValueError('official pagination incomplete')
        dates=[r[0]for r in p['kline']]
        if dates!=sorted(set(dates)):raise ValueError('duplicate or unsorted dates')
        prices={}
        for day,close,prev,chg,vol,amount in p['kline']:
            d=f'{str(day)[:4]}-{str(day)[4:6]}-{str(day)[6:]}'
            if not e['start']<=d<=e['through']:continue
            if min(close,prev,vol,amount)<=0 or abs((D(close)/D(prev)-1)*100-D(chg))>D('.015'):raise ValueError('invalid activity or price')
            prices[d]=D(close)
        historical=item['historical_primary_raw'];recent=item['later_primary_paired']
        if set(prices)!=set(historical)|set(recent) or set(historical)&set(recent):raise ValueError('comparison dates changed')
        for d,v in historical.items():
            if prices[d]!=D(v) or prices[d]!=D(item['historical_tencent_raw'][d]):raise ValueError('historical raw mismatch')
        for d,v in recent.items():
            if prices[d]!=D(item['later_tencent_paired'][d]) or abs(prices[d]-D(v))>D('1e-12'):raise ValueError('later paired close mismatch')
        counts.append({'symbol':code,'historical':len(historical),'later':len(recent),'total':len(prices)})
    if len({r['symbol']for r in counts})!=len(counts):raise ValueError('duplicate security')
    return counts
