"""Five source-bound longitudinal price checks, without expanding the main-board cohort."""
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from math import prod
from canonical_json import digest

SUBJECTS={'603398':'沐邦','002514':'宝馨','600363':'联光','002667':'威领','688053':'思科瑞'}


def price_scope_digest(inputs):
    return digest({k:inputs[k] for k in ('calendar','through','fixed_prices','benchmarks','members')})


def quotes_from_source(source):
    raw=source['raw_text']
    if sha256(raw.encode()).hexdigest()!=source['sha256']:raise ValueError('stock quote original changed')
    x=json.loads(raw);symbol=source['symbol'];key=source['key'];ticker=('sh' if symbol.startswith('6') else 'sz')+symbol
    if key.startswith('tencent_'):
        block=x.get('data',{}).get(ticker,{})
        identity=block.get('qt',{}).get(ticker) or []
        if len(identity)<3 or identity[2]!=symbol:raise ValueError('stock quote identity changed')
        rows=(block.get('qfqday') or block.get('day') or []) if key=='tencent_qfq' else block.get('day') or []
    elif key.startswith('eastmoney_'):
        block=x.get('data') or {}
        if block.get('code')!=symbol or block.get('market')!=(1 if symbol.startswith('6') else 0):raise ValueError('stock quote identity changed')
        rows=[s.split(',') for s in block.get('klines',[])]
    else:raise ValueError('unknown quote channel')
    quotes={}
    for row in rows:
        d=row[0];close=Decimal(row[2]);vol=Decimal(row[5])
        if d in quotes or not close.is_finite() or close<=0 or not vol.is_finite() or vol<=0:raise ValueError('nontraded, invalid or duplicate public stock quote')
        quotes[d]=close
    return quotes


def halt_explanation(packet,symbol,calendar,base,through):
    rows=[r for r in packet.get('halt_explanations',[]) if r['symbol']==symbol]
    if not rows:return None
    if len(rows)!=1:raise ValueError('duplicate halt explanation')
    row=rows[0]
    if not row.get('facts'):raise ValueError('halt explanation lacks primary facts')
    if row['cause_key'] not in ('offer_result_confirmation','warning_implementation'):raise ValueError('unknown halt cause')
    start,resume=row['start'],row['resume']
    if start not in calendar or resume not in calendar or not(start<resume<=through):raise ValueError('halt dates outside verified calendar')
    if not(row['halt_disclosed_on']<=start and row['resume_disclosed_on']<=resume):raise ValueError('halt/resume disclosure timing invalid')
    facts=[*row['facts'],*([row['later_verified_event']] if row.get('later_verified_event') else [])]
    for fact in facts:
        source=fact['source']
        if fact['published_on']>through or not all(source.get(k) for k in ('title','url','sha256','page')):raise ValueError('halt fact lacks timely primary source')
    covered=[d for d in calendar if start<=d<resume]
    actual_resume=next((d for d in calendar if d>=start and base[d]['has_trade']),None)
    prior=next((d for d in reversed(calendar) if d<start and base[d]['has_trade']),None)
    matches=all(not base[d]['has_trade'] for d in covered) and actual_resume==resume
    return {**row,'market_halt_dates':covered,'market_halt_days':len(covered),'previous_actual_close_date':prior,'first_actual_resume_date':actual_resume,'schedule_matches_quotes':matches,'continuous_episode_count':1}


def price_check_view(inputs,daily):
    packet=inputs.get('stock_price_crosscheck')
    if packet is None:return None
    if packet['content_digest']!=digest({k:v for k,v in packet.items() if k!='content_digest'}):raise ValueError('stock price packet changed')
    if packet['price_scope_digest']!=price_scope_digest(inputs):raise ValueError('stock price scope changed')
    calendar=inputs['calendar'];end=inputs['through'];companies=packet['original_prices']['companies']
    halts=packet.get('halt_explanations',[])
    if len({r['symbol'] for r in halts})!=len(halts) or not {r['symbol'] for r in halts}<=set(SUBJECTS):raise ValueError('halt research scope changed')
    if packet['original_prices']['calendar']!=calendar or packet['original_prices']['through']!=end:raise ValueError('original quote scope changed')
    if len(companies)!=5 or {c['symbol'] for c in companies}!=set(SUBJECTS):raise ValueError('five research subjects changed')
    result=[];point_count=0
    for c in companies:
        symbol=c['symbol'];rows=c['rows'];base={r['date']:r for r in rows}
        if [r['date'] for r in rows]!=calendar or c['qfq_normalization_date']!=end:raise ValueError('original quote calendar or qfq cutoff changed')
        for r in rows:
            if r['has_trade']!=bool(r['volume'] is not None and r['volume']>0):raise ValueError('original activity changed')
            expected=float(Decimal(str(r['raw_close']))*Decimal(str(r['adj_factor']))/Decimal(str(c['qfq_normalization_factor']))) if r['raw_close'] is not None and r['adj_factor'] else None
            if expected!=r['qfq_close']:raise ValueError('qfq normalization changed')
        traded={r['date'] for r in rows if r['has_trade']};channels=[];seen=set();maps={}
        for s in [s for s in packet['sources'] if s['symbol']==symbol]:
            if s['key'] in seen:raise ValueError('duplicate stock quote channel')
            seen.add(s['key']);q=quotes_from_source(s);maps[s['key']]=q
            if set(q)-set(calendar):raise ValueError('quote outside declared window')
            diffs=[]
            for d in sorted(set(q)&traded):
                field='qfq_close' if s['key'].endswith('qfq') else 'raw_close';a=Decimal(str(base[d][field]));b=q[d]
                if b!=a.quantize(Decimal('.01'),rounding=ROUND_HALF_UP):diffs.append({'date':d,'original_close':float(a),'checked_close':float(b),'difference':float(b-a)})
            missing=sorted(traded-set(q));extra=sorted(set(q)-traded);point_count+=len(q)
            channels.append({'key':s['key'],'points':len(q),'matched_points':len(set(q)&traded)-len(diffs),'missing_trade_dates':missing,'extra_nontrade_dates':extra,'price_differences':diffs,'url':s['url'],'sha256':s['sha256'],'observed_at':s['observed_at']})
        if not {'tencent_raw','tencent_qfq','eastmoney_qfq'}<=seen:raise ValueError('required raw and two qfq channels missing')
        gaps=[{'date':r['date'],'has_reference_close':r['raw_close'] is not None,'provider_reports_suspension':any(x['suspend_type']=='S' for x in r['suspension_records'])} for r in rows if not r['has_trade']]
        windows={}
        for label,anchor in [('all','2026-07-03'),('20',calendar[-21]),('5',calendar[-6])]:
            a,b=base[anchor],base[end];selected=[r for r in daily if anchor<r['date']<=end];actual=a['has_trade'] and b['has_trade'];stock=(b['qfq_close']/a['qfq_close']-1)*100 if actual else None
            market=(prod(1+r['market_pct']/100 for r in selected)-1)*100;st=(prod(1+r['return_pct']/100 for r in selected)-1)*100
            verified={key:(float(q[end]/q[anchor]-1)*100 if anchor in q and end in q else None) for key,q in maps.items()}
            prior=next((r for r in reversed(rows) if r['date']<anchor and r['has_trade']),None) if not a['has_trade'] else None
            alternative=None
            if prior and b['has_trade']:
                altrows=[r for r in daily if prior['date']<r['date']<=end]
                alternative={'anchor':prior['date'],'through':end,'market_days':len(altrows),'actual_trading_days':sum(r['has_trade'] for r in rows if prior['date']<r['date']<=end),'stock_pct':(b['qfq_close']/prior['qfq_close']-1)*100,'market_pct':(prod(1+r['market_pct']/100 for r in altrows)-1)*100,'st_pct':(prod(1+r['return_pct']/100 for r in altrows)-1)*100,'not_same_window':True}
            windows[label]={'anchor':anchor,'through':end,'market_days':len(selected),'stock_pct':stock,'reference_price_change_pct':(b['qfq_close']/a['qfq_close']-1)*100 if a['qfq_close'] and b['qfq_close'] else None,'market_pct':market,'st_pct':st,'market_excess_pp':stock-market if stock is not None else None,'st_excess_pp':stock-st if stock is not None else None,'checked_returns':verified,'gap':None if actual else '共同日期起点没有实际成交；参考价变化另列，不充当成交端点','alternative_actual_anchor':alternative}
        frozen=[r for r in inputs['fixed_prices'] if r['symbol']==symbol];frozen_conflicts=[r['trade_date'] for r in frozen if (r.get('has_trade') is not base[r['trade_date']]['has_trade']) or r.get('has_trade') is True and (r['trade_date'] not in traded or Decimal(str(r['close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=Decimal(str(base[r['trade_date']]['qfq_close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))]
        initial=any(r['symbol']==symbol and r['trade_date']=='2026-07-03' for r in inputs['members']);scope='longitudinal_star' if symbol.startswith('688') else 'fixed_main_board' if initial else 'entrant_main_board'
        result.append({'halt_evidence':halt_explanation(packet,symbol,calendar,base,end),'symbol':symbol,'name':SUBJECTS[symbol],'scope':scope,'traded_days':len(traded),'calendar_days':len(calendar),'factor_change_dates':[r['date'] for n,r in enumerate(rows) if n and r['adj_factor']!=rows[n-1]['adj_factor']],'raw_qfq_differ_days':sum(r['has_trade'] and r['raw_close']!=r['qfq_close'] for r in rows),'gaps':gaps,'channels':channels,'frozen_price_points':len(frozen),'frozen_price_conflicts':frozen_conflicts,'windows':windows,'all_available_prices_agree':not frozen_conflicts and all(not c['price_differences'] and not c['missing_trade_dates'] and not c['extra_nontrade_dates'] for c in channels)})
    return {'start':calendar[0],'through':end,'rows':result,'subjects':len(result),'unique_trade_dates':sum(r['traded_days'] for r in result),'quote_points':point_count,'valid_responses':len(packet['sources']),'failed_requests':packet['failed_requests'],'all_available_prices_agree':all(r['all_available_prices_agree'] for r in result),'recent_five_up':sum(r['windows']['5']['stock_pct'] is not None and r['windows']['5']['stock_pct']>0 for r in result),'recent_twenty_down':sum(r['windows']['20']['stock_pct'] is not None and r['windows']['20']['stock_pct']<0 for r in result),'recent_twenty_unavailable':sum(r['windows']['20']['stock_pct'] is None for r in result),'boundary':'本轮仅核5个明确对象，不代表156家公司全量认证。跨报价渠道不证明底层独立；复权因子按11月6日归一，仅作截至本轮的回看口径，不冒充历史当时已知。无成交端点不补零，参考价与另起日期的观察分别标明。价格核对不证明公司程序、财务改善或公告因果。'}
