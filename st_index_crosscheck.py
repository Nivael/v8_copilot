"""Source-bound cross-channel checks; preserve discrepancies without replacing prices."""
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from math import prod
from canonical_json import digest

IDENTITIES={'000985':('csi_all_share','中证全指'),'932000':('csi_2000','中证2000')}


def benchmark_scope_digest(inputs):
    return digest({k:inputs[k] for k in ('calendar','through','benchmarks')})


def parse_quotes(source):
    raw=source['raw_text']
    if sha256(raw.encode()).hexdigest()!=source['sha256']:
        raise ValueError('index raw source digest changed')
    data=json.loads(raw);symbol=source['symbol'];vendor=source['vendor']
    if symbol not in IDENTITIES:raise ValueError('unknown benchmark identity')
    if vendor=='tencent':
        block=data.get('data',{}).get('sh'+symbol,{})
        identity=block.get('qt',{}).get('sh'+symbol) or []
        if len(identity)<3 or identity[1:3]!=[IDENTITIES[symbol][1],symbol]:raise ValueError('index source identity mismatch')
        rows=block.get('day') or []
    elif vendor=='eastmoney':
        block=data.get('data') or {}
        if block.get('code')!=symbol or block.get('name')!=IDENTITIES[symbol][1] or block.get('market')!=(1 if symbol=='000985' else 2):raise ValueError('index source identity mismatch')
        rows=[r.split(',') for r in block.get('klines',[])]
    else:raise ValueError('unknown index quote channel')
    quotes={}
    for row in rows:
        day,close=row[0],Decimal(row[2])
        if day in quotes or not close.is_finite() or close<=0:raise ValueError('invalid or duplicate index quote')
        quotes[day]=close
    return quotes


def crosscheck_view(inputs,daily):
    packet=inputs.get('index_crosscheck')
    if packet is None:return None
    if packet['content_digest']!=digest({k:v for k,v in packet.items() if k!='content_digest'}):raise ValueError('index check packet changed')
    if packet['benchmark_scope_digest']!=benchmark_scope_digest(inputs):raise ValueError('index benchmark scope changed')
    calendar=inputs['calendar'];last=inputs['through'];rows=[];seen=set()
    for source in packet['sources']:
        pair=(source['symbol'],source['vendor'])
        if pair in seen:raise ValueError('duplicate quote channel')
        seen.add(pair)
        if source['observed_at'][:10]<last:raise ValueError('quote observation predates cutoff')
        code,name=IDENTITIES[source['symbol']];q=parse_quotes(source)
        base={r['trade_date']:Decimal(str(r['close'])) for r in inputs['benchmarks'] if r['benchmark_id']==code}
        if set(q)!=set(calendar) or set(base)!=set(calendar):raise ValueError('index source calendar incomplete or extra')
        details=[];rounded=0;exact=0;max_diff=Decimal(0)
        for d in calendar:
            delta=q[d]-base[d];max_diff=max(max_diff,abs(delta));same=q[d]==base[d]
            same_round=q[d]==base[d].quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            exact+=same;rounded+=same_round
            if not same_round:details.append({'date':d,'original_close':float(base[d]),'checked_close':float(q[d]),'difference_points':float(delta)})
        daily_diffs=[float((q[d]/q[calendar[n-1]]-base[d]/base[calendar[n-1]])*100) for n,d in enumerate(calendar) if n]
        boundary_changes=[]
        for n,d in enumerate(calendar[1:],1):
            a=float((base[d]/base[calendar[n-1]]-1)*100);b=float((q[d]/q[calendar[n-1]]-1)*100)
            if (a>0,a<0,a<-1)!=(b>0,b<0,b<-1):boundary_changes.append({'date':d,'original_pct':a,'checked_pct':b})
        windows=[]
        for label,days in [('20',20),('40',40),('all',None)]:
            for phase in ('before','after'):
                eligible=[r['date'] for r in daily if (r['date']<'2026-07-06')==(phase=='before')]
                selected=eligible[-(days or 40):] if phase=='before' else eligible[:days] if days else eligible
                anchor=calendar[calendar.index(selected[0])-1];end=selected[-1]
                original=float((base[end]/base[anchor]-1)*100);checked=float((q[end]/q[anchor]-1)*100)
                st=(prod(1+r['return_pct']/100 for r in daily if anchor<r['date']<=end)-1)*100
                windows.append({'key':label,'phase':phase,'anchor':anchor,'through':end,'days':len(selected),'original_pct':original,'checked_pct':checked,'difference_pp':checked-original,'st_pct':st,'excess_direction_unchanged':(st-original>0)==(st-checked>0) and (st-original<0)==(st-checked<0),'direction_unchanged':(original>0)==(checked>0) and (original<0)==(checked<0)})
        rows.append({'symbol':source['symbol'],'name':name,'vendor':source['vendor'],'observations':len(q),'exact_points':exact,'rounding_agree_points':rounded,'precision_difference_count':len(details),'precision_differences':details,'max_close_difference_points':float(max_diff),'environment_boundary_changes':boundary_changes,'max_daily_difference_pp':max(abs(x) for x in daily_diffs),'max_window_difference_pp':max(abs(w['difference_pp']) for w in windows),'windows':windows,'all_window_directions_unchanged':all(w['direction_unchanged'] and w['excess_direction_unchanged'] for w in windows),'source':{k:source[k] for k in ('url','sha256','observed_at')}})
    if {r['symbol'] for r in rows}!=set(IDENTITIES):raise ValueError('both benchmark checks required')
    return {'start':calendar[0],'through':last,'rows':rows,'index_count':len({r['symbol'] for r in rows}),'quote_points':sum(r['observations'] for r in rows),'unique_index_dates':len(calendar)*2,'precision_difference_count':sum(r['precision_difference_count'] for r in rows),'all_window_directions_unchanged':all(r['all_window_directions_unchanged'] for r in rows),'max_window_difference_pp':max(r['max_window_difference_pp'] for r in rows),'boundary':'这是不同公开报价渠道的交叉核对，不证明底层供数完全独立；不能替代156家公司日线与全体成员核验。原始高精度行情保留，未覆盖或超过舍入的差异不改写为完全一致。报价接近不认证公告或制度因果。','empty_routes':packet['empty_routes'],'identity_sources':packet['identity_sources']}
