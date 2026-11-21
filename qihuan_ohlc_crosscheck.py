"""Official SZSE OHLC corroboration, with a narrower post-window observation."""
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
from datetime import date
import gzip
import json
from market_calendar import sessions_2026


def crosscheck(e, folder):
    folder=Path(folder)
    raw=e['official_text'].encode()
    if sha256(raw).hexdigest()!=e['official_source']['sha256']or len(raw)!=e['official_source']['bytes']:raise ValueError('official bytes changed')
    ref=e['official_source']
    if ref['params']!={'cycleType':32,'marketId':1,'code':'000826'}or ref['url']!='https://www.szse.cn/api/market/ssjjhq/getHistoryData?cycleType=32&marketId=1&code=000826':raise ValueError('official request identity changed')
    body=json.loads(raw)
    if str(body['code'])!='0'or body['data']['code']!='000826':raise ValueError('official source failed or identity changed')
    prices={}
    for row in body['data']['picupdata']:
        if len(row)!=9 or row[0]in prices:raise ValueError('official schema or duplicate date')
        op,cl,lo,hi=map(D,row[1:5])
        if min(op,cl,lo,hi)<=0 or not lo<=min(op,cl)<=max(op,cl)<=hi or D(str(row[7]))<=0:raise ValueError('official OHLC invalid')
        prices[row[0]]={'open':op,'close':cl,'low':lo,'high':hi}
    days=sessions_2026(date(2026,11,9),date(2026,11,19));refs=e['provider_refs']
    if sorted(r['params']['trade_date']for r in refs)!=[d.replace('-','')for d in days]:raise ValueError('all nine provider days required')
    matched=[]
    for ref in refs:
        raw=gzip.decompress((folder/(ref['response_sha256']+'.json.gz')).read_bytes())
        if sha256(raw).hexdigest()!=ref['response_sha256']or len(raw)!=ref['bytes']:raise ValueError('provider bytes changed')
        payload=json.loads(raw)
        if ref['api_name']!='daily'or payload['code']!=0 or payload['data']['fields']!=ref['fields'].split(','):raise ValueError('provider identity/fields changed')
        candidates=[dict(zip(payload['data']['fields'],r,strict=True))for r in payload['data']['items']if r[0]=='000826.SZ']
        if len(candidates)!=1:raise ValueError('provider subject missing or duplicate')
        row=candidates[0];compact=ref['params']['trade_date'];day=f'{compact[:4]}-{compact[4:6]}-{compact[6:]}'
        if row['trade_date']!=compact or day not in prices:raise ValueError('day mismatch')
        if any(D(str(row[k]))!=prices[day][k]for k in ('open','close','low','high')):raise ValueError('cross-channel OHLC conflict')
        matched.append(day)
    if '2026-11-20'not in prices:raise ValueError('new observation missing; do not keep old boundary claim')
    new=prices['2026-11-20'];one=len(set(new.values()))==1
    return {'version':'qihuan_official_ohlc_crosscheck_v1','symbol':'000826.SZ',
            'paired_start':days[0],'paired_through':days[-1],'paired_ohlc_days':len(matched),
            'paired_ohlc_values':len(matched)*4,
            'one_price_dates':[d for d in days if len(set(prices[d].values()))==1],
            'new_day':{'date':'2026-11-20',**{k:str(v)for k,v in new.items()},'one_observed_price':one,
                       'single_price_streak_observed_end':'2026-11-19'if not one else None,
                       'close_at_actual_down_limit':None},
            'boundary':'九日OHLC跨渠道相同，实际下限价仍来自保存供应商原件；官网日线本身没有实际限价字段。20日不再全天同价可由高低不同确认，不据此断言20日收盘是否达到实际下限价或真实退出能力；不推进整组共同窗口。',
            'independent_validations_added':0}
