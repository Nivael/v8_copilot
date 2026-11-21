"""Point-in-time provider cohorts paired to saved raw OHLC and actual limits."""
from datetime import date
from decimal import Decimal as D, InvalidOperation
from hashlib import sha256
from pathlib import Path
from collections import Counter
import gzip
import json
from market_calendar import sessions_2026

FIELDS={'daily':'ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount',
        'stk_limit':'trade_date,ts_code,pre_close,up_limit,down_limit',
        'stock_st':'ts_code,name,trade_date,type,type_name'}


def main_board(symbol):
    return symbol.endswith(('.SH','.SZ')) and symbol[:3] in ('000','001','002','003','600','601','603','605')


def replay(manifest, folder):
    folder=Path(folder);days=sessions_2026(date(2026,11,9),date(2026,11,19));tables={}
    for ref in manifest['sources']:
        api=ref['api_name'];compact=ref['params'].get('trade_date');day=f'{compact[:4]}-{compact[4:6]}-{compact[6:]}'
        if api not in FIELDS or day not in days or ref['params']!={'trade_date':compact} or ref['fields']!=FIELDS[api]:
            raise ValueError('source request changed')
        key=(day,api)
        if key in tables:raise ValueError('duplicate source day/api')
        raw=gzip.decompress((folder/(ref['response_sha256']+'.json.gz')).read_bytes())
        if len(raw)!=ref['bytes'] or sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('source bytes changed')
        p=json.loads(raw)
        if p['code']!=0 or p['data']['fields']!=FIELDS[api].split(','):raise ValueError('response failed or fields changed')
        items=p['data']['items']
        if len(items)>=(1000 if api=='stock_st' else 6000):raise ValueError('provider row cap reached')
        rows={}
        for item in items:
            row=dict(zip(p['data']['fields'],item,strict=True));code=row['ts_code']
            if code in rows or row['trade_date']!=compact:raise ValueError('duplicate security or wrong date')
            rows[code]=row
        tables[key]=rows
    if set(tables)!={(d,a)for d in days for a in FIELDS}:raise ValueError('all 27 source responses required')
    fixed=manifest['fixed_symbols']
    if len(fixed)!=150 or len(set(fixed))!=150 or not all(main_board(c)for c in fixed):raise ValueError('fixed 150 scope changed')
    def number(v):
        try:n=D(str(v))
        except InvalidOperation:raise ValueError('invalid numeric value')
        if not n.is_finite():raise ValueError('invalid numeric value')
        return n
    groups=[]
    for key in ('daily_members','fixed150'):
        daily=[];details=[]
        for day in days:
            members=tables[day,'stock_st'];quotes=tables[day,'daily'];limits=tables[day,'stk_limit']
            selected=sorted(c for c in members if main_board(c)) if key=='daily_members' else fixed
            rows=[]
            for code in selected:
                row={'date':day,'symbol':code,'in_saved_daily_st':code in members,'name':members.get(code,{}).get('name')}
                q=quotes.get(code);limit=limits.get(code)
                row['limit_row_present']=limit is not None
                if q is None:row['status']='missing_daily'
                elif number(q['vol'])<=0:row['status']='nontrading_daily'
                elif limit is None:row['status']='missing_limit'
                else:
                    p={k:number(q[k])for k in ('open','high','low','close','pre_close')}
                    l={k:number(limit[k])for k in ('pre_close','up_limit','down_limit')}
                    if min(p.values())<=0 or min(l.values())<=0 or not l['down_limit']<=l['pre_close']<=l['up_limit'] or not p['low']<=min(p['open'],p['close'])<=max(p['open'],p['close'])<=p['high']:
                        row['status']='invalid_price_bounds'
                    elif p['pre_close']!=l['pre_close']:
                        row['status']='reference_conflict'
                    elif p['low']<l['down_limit'] or p['high']>l['up_limit']:
                        row['status']='ohlc_limit_conflict'
                    else:
                        row.update(status='paired',close_at_down=p['close']==l['down_limit'],touch_down=p['low']==l['down_limit'],
                                   one_price_down=all(p[k]==l['down_limit']for k in ('open','high','low','close')),
                                   close_at_up=p['close']==l['up_limit'],
                                   close=str(q['close']),low=str(q['low']),high=str(q['high']),down_limit=str(limit['down_limit']),up_limit=str(limit['up_limit']))
                rows.append(row)
            counts=Counter(r['status']for r in rows);paired=[r for r in rows if r['status']=='paired']
            trading=len(rows)-counts['missing_daily']-counts['nontrading_daily']
            daily.append({'date':day,'members':len(rows),'trading_daily_rows':trading,
                          'limit_rows':sum(r['limit_row_present']for r in rows),'paired':len(paired),
                          'missing_daily':counts['missing_daily'],'nontrading_daily':counts['nontrading_daily'],
                          'unresolved_trading':trading-len(paired),
                          'close_at_down':sum(r['close_at_down']for r in paired),'touch_down':sum(r['touch_down']for r in paired),
                          'one_price_down':sum(r['one_price_down']for r in paired),'close_at_up':sum(r['close_at_up']for r in paired)})
            details.extend(rows)
        groups.append({'key':key,'days':daily,'rows':details})
    return {'version':'st_limit_cohorts_v1','start':days[0],'through':days[-1],'groups':groups,
            'boundary':'每日组按保存供应商当日ST名单筛主板；不是完整官方法定名录。固定150组保留退出/停牌或缺价样本；无日线记录不等于停牌、退市或零次跌停。分母仅有成交日线且限价与OHLC配对通过的股票；有成交也不证明委托可成交。',
            'independent_validations_added':0}
