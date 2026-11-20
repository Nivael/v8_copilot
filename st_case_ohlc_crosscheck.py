"""Selected SSE cases: raw OHLC across providers, official closes as a separate control."""
from decimal import Decimal as D
from datetime import date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
import gzip
import json
from market_calendar import sessions_2026

CODES={'600180','600340','603359'}


def crosscheck(e, folder):
    folder=Path(folder);days=sessions_2026(date(2026,11,9),date(2026,11,19));new_day='2026-11-20';provider={}
    if sorted(r['params']['trade_date']for r in e['provider_refs'])!=[d.replace('-','')for d in days]:raise ValueError('all nine provider days required')
    for ref in e['provider_refs']:
        raw=gzip.decompress((folder/(ref['response_sha256']+'.json.gz')).read_bytes())
        if len(raw)!=ref['bytes']or sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('provider bytes changed')
        p=json.loads(raw);fields=ref['fields'].split(',')
        if ref['api_name']!='daily'or p['code']!=0 or p['data']['fields']!=fields:raise ValueError('provider fields/identity changed')
        for item in p['data']['items']:
            row=dict(zip(fields,item,strict=True));code=row['ts_code'][:6]
            if code not in CODES:continue
            if row['trade_date']!=ref['params']['trade_date']:raise ValueError('provider date changed')
            day=f"{row['trade_date'][:4]}-{row['trade_date'][4:6]}-{row['trade_date'][6:]}";key=(code,day)
            if key in provider:raise ValueError('duplicate provider observation')
            provider[key]={k:D(str(row[k]))for k in ('open','close','high','low')}
    if {s['symbol']for s in e['raw_ohlc_sources']}!=CODES or len(e['raw_ohlc_sources'])!=3 or {s['symbol']for s in e['sse_close_sources']}!=CODES or len(e['sse_close_sources'])!=3:raise ValueError('three selected source identities required')
    official={}
    def original(src):
        raw=src['text'].encode()
        if sha256(raw).hexdigest()!=src['sha256']or len(raw)!=src['bytes']:raise ValueError('source bytes changed')
        return json.loads(raw)
    for src in e['sse_close_sources']:
        p=original(src);code=src['symbol']
        if p['code']!=code or src['url']!='https://yunhq.sse.com.cn:32042/v1/sh1/dayk/'+code or src['params']!={'select':'date,close,prevClose,chg_rate,volume,amount','begin':-126,'end':-1,'period':'day'}:raise ValueError('SSE identity/request changed')
        seen=set()
        for row in p['kline']:
            if len(row)!=6 or row[0]in seen:raise ValueError('SSE row schema/duplicate changed')
            seen.add(row[0]);compact=str(row[0]);day=f'{compact[:4]}-{compact[4:6]}-{compact[6:]}'
            if day in days+[new_day]:
                if D(str(row[1]))<=0 or D(str(row[4]))<=0:raise ValueError('SSE selected close/trade invalid')
                official[code,day]=D(str(row[1]))
    cases=[]
    for src in e['raw_ohlc_sources']:
        code=src['symbol'];ticker='sh'+code;p=original(src);params={'param':f'{ticker},day,2026-11-06,2026-11-20,320,'}
        if src['url']!='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode(params)or src['params']!=params or p['code']!=0:raise ValueError('raw OHLC identity/request changed')
        block=p['data'][ticker]
        if block['qt'][ticker][2]!=code or 'day'not in block:raise ValueError('raw unadjusted OHLC required')
        parsed={}
        for row in block['day']:
            if len(row)!=6 or row[0]in parsed:raise ValueError('raw OHLC row schema/duplicate changed')
            op,cl,hi,lo,volume=map(D,row[1:])
            if min(op,cl,hi,lo,volume)<=0 or not lo<=min(op,cl)<=max(op,cl)<=hi:raise ValueError('raw OHLC invalid')
            parsed[row[0]]={'open':op,'close':cl,'high':hi,'low':lo}
        for day in days:
            if (code,day)not in provider or day not in parsed or provider[code,day]!=parsed[day]:raise ValueError('provider/raw OHLC conflict or missing day')
        for day in days+[new_day]:
            if day not in parsed or official.get((code,day))!=parsed[day]['close']:raise ValueError('SSE close conflict or missing day')
        new=parsed[new_day];old=parsed[days[-1]]['close']
        cases.append({'symbol':code+'.SH','name':block['qt'][ticker][1],'matched_ohlc_days':len(days),'matched_ohlc_values':len(days)*4,'sse_close_control_days':len(days)+1,
                      'one_price_dates':[d for d in days if len(set(parsed[d].values()))==1],
                      'new_day':{'date':new_day,**{k:str(v)for k,v in new.items()},'previous_observed_close':str(old),
                                 'one_observed_price':len(set(new.values()))==1,'close_vs_previous':'higher'if new['close']>old else'lower'if new['close']<old else'flat',
                                 'actual_down_limit':None}})
    return {'version':'selected_sse_ohlc_crosscheck_v1','paired_start':days[0],'paired_through':days[-1],'new_day':new_day,'cases':sorted(cases,key=lambda x:x['symbol']),
            'boundary':'三家九日原始OHLC由另一行情渠道核同，另用保存上交所收盘控制到20日；官方收盘不冒充完整OHLC或实际限价。20日只补各公司日线，整组窗口不推进，实际限价字段、历史队列与执行仍另核。跨渠道同案例不增加独立经验验证。','independent_validations_added':0}
