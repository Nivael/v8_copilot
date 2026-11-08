"""Post-selected warning-removal cohort: same issuers, windows and explicit quote differences."""
from collections import Counter
from decimal import Decimal,ROUND_HALF_UP
from math import prod,isclose
from statistics import mean,median
from itertools import combinations
from canonical_json import digest
from st_member_transitions import member_transition_view
from st_stock_price_crosscheck import quotes_from_source

HORIZONS=(1,5,20,40)
def scope_digest(i):
 return digest({k:i[k] for k in ('calendar','through','fixed_prices','activities','benchmarks','member_transitions')})

def removal_cohort_view(i,daily):
 p=i.get('removal_cohort')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('removal cohort source/scope changed')
 transition=member_transition_view(i);targets=[r for r in transition['rows'] if r['status']=='warning_removed'];excluded=[r for r in transition['rows'] if r['status']!='warning_removed'];symbols={r['symbol'] for r in targets};original=p['original_prices'];cal=i['calendar'];end=i['through']
 if len(symbols)!=len(targets) or {c['symbol'] for c in original['companies']}!=symbols or len(original['companies'])!=len(symbols) or original['calendar']!=cal or original['through']!=end:raise ValueError('removal cohort identities/calendar changed')
 source_refs=p['sources']
 if any(r['symbol'] not in symbols for r in source_refs):raise ValueError('quote subject outside removal cohort')
 rows=[]
 for t in targets:
  s=t['symbol'];company=next(c for c in original['companies'] if c['symbol']==s);base={r['date']:r for r in company['rows']}
  if [r['date'] for r in company['rows']]!=cal or company['qfq_normalization_date']!=end:raise ValueError('cohort price calendar changed')
  for r in base.values():
   if r['has_trade']!=bool(r['volume'] is not None and r['volume']>0):raise ValueError('cohort trade flag changed')
   expected=float(Decimal(str(r['raw_close']))*Decimal(str(r['adj_factor']))/Decimal(str(company['qfq_normalization_factor']))) if r['raw_close'] is not None and r['adj_factor'] else None
   if r['qfq_close']!=expected:raise ValueError('cohort adjusted calculation changed')
  traded={d for d,r in base.items() if r['has_trade']};frozen={r['trade_date']:r for r in i['fixed_prices'] if r['symbol']==s};frozen_conflicts=sorted(d for d,r in frozen.items() if r['has_trade']!=base[d]['has_trade'] or r['has_trade'] and not isclose(r['close'],base[d]['qfq_close'],rel_tol=0,abs_tol=1e-12))
  if traded-set(frozen):frozen_conflicts+=sorted(traded-set(frozen))
  sources=[r for r in source_refs if r['symbol']==s];keys={r['key'] for r in sources}
  if len(keys)!=len(sources) or not keys<={'tencent_raw','tencent_qfq'}:raise ValueError('cohort quote channel identity changed')
  channels=[];maps={}
  for ref in sources:
   q=quotes_from_source(ref);maps[ref['key']]=q
   if set(q)-set(cal):raise ValueError('cohort quote outside calendar')
   diffs=[]
   for d in sorted(set(q)&traded):
    value=Decimal(str(base[d]['qfq_close' if ref['key'].endswith('qfq') else 'raw_close']));expected=value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    if q[d]!=expected:diffs.append({'date':d,'original_close':str(value),'original_cent_close':str(expected),'checked_close':str(q[d]),'difference':str(q[d]-value)})
   channels.append({'key':ref['key'],'points':len(q),'matched_points':len(set(q)&traded)-len(diffs),'missing_trade_dates':sorted(traded-set(q)),'extra_nontrade_dates':sorted(set(q)-traded),'price_differences':diffs,'source':{k:ref[k] for k in ('url','sha256','observed_at')},'reused':ref.get('reused',False)})
  previous=max((d for d in cal if d<t['suspend_on'] and d in traded),default=None);resume=min((d for d in traded if d>=t['suspend_on']),default=None)
  halt_dates=[d for d in cal if t['suspend_on']<=d<t['effective_on']]
  stage_matches=bool(previous and resume==t['effective_on'] and all(d not in traded for d in halt_dates))
  def window(a,b,n):
   if a is None or b is None:
    available=sum(d>a for d in cal) if a else 0
    return {'anchor':a,'through':None,'requested_days':n,'market_days':None,'available_market_days':available,'stock_traded_days':None,'stock_pct':None,'market_pct':None,'st_pct':None,'market_excess_pp':None,'st_excess_pp':None,'status':'insufficient_followup' if a else 'insufficient_history','quote_endpoint_supported':False,'checked_qfq_pct':None,'quote_return_difference_pp':None,'nontrade_dates':[]}
   ds=[r for r in daily if a<r['date']<=b];actual=[d for d in cal if a<d<=b];usable=a in traded and b in traded and a in frozen and b in frozen
   stock=(frozen[b]['close']/frozen[a]['close']-1)*100 if usable else None;market=(prod(1+x['market_pct']/100 for x in ds)-1)*100;st=(prod(1+x['return_pct']/100 for x in ds)-1)*100
   if len(ds)!=len(actual) or n is not None and len(ds)!=n:raise ValueError('window not full market calendar')
   q=maps.get('tencent_qfq',{});quote=float((q[b]/q[a]-1)*100) if usable and a in q and b in q else None
   endpoints=bool(quote is not None and all(q[d]==Decimal(str(base[d]['qfq_close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) for d in (a,b)))
   return {'anchor':a,'through':b,'requested_days':n,'market_days':len(ds),'available_market_days':len(ds),'stock_traded_days':sum(d in traded for d in actual),'stock_pct':stock,'market_pct':market,'st_pct':st,'market_excess_pp':stock-market if stock is not None else None,'st_excess_pp':stock-st if stock is not None else None,'status':'valid' if usable else 'nontraded_or_missing_endpoint','quote_endpoint_supported':endpoints and stage_matches and not frozen_conflicts,'checked_qfq_pct':quote,'quote_return_difference_pp':quote-stock if quote is not None else None,'nontrade_dates':[d for d in actual if d not in traded]}
  idx=cal.index(previous) if previous else None;ri=cal.index(resume) if resume else None;windows={}
  for n in HORIZONS:
   windows[str(n)]={'before':window(cal[idx-n] if idx is not None and idx>=n else None,previous,n),'after':window(previous,cal[idx+n] if idx is not None and idx+n<len(cal) else None,n),'from_resume_close':window(resume,cal[ri+n] if ri is not None and ri+n<len(cal) else None,n)}
  rows.append({'symbol':s,'name':t['new_name'],'anchor_name':t['anchor_name'],'warning_removed':t['warning_removed'],'announced_on':t['announced_on'],'suspend_on':t['suspend_on'],'effective_on':t['effective_on'],'pre_halt_close_on':previous,'first_resume_close_on':resume,'halt_dates':halt_dates,'halt_and_resume_match':stage_matches,'facts':t['facts'],'windows':windows,'first_resume_change':window(previous,resume,None),'to_cutoff':window(previous,end,None),'channels':channels,'frozen_price_conflicts':frozen_conflicts,'all_original_raw_prices_agree':any(c['key']=='tencent_raw' for c in channels) and all(not c['price_differences'] and not c['missing_trade_dates'] and not c['extra_nontrade_dates'] for c in channels if c['key']=='tencent_raw'),'all_qfq_prices_agree':any(c['key']=='tencent_qfq' for c in channels) and all(not c['price_differences'] and not c['missing_trade_dates'] and not c['extra_nontrade_dates'] for c in channels if c['key']=='tencent_qfq'),'factor_change_dates':[r['date'] for n,r in enumerate(company['rows']) if n and r['adj_factor']!=company['rows'][n-1]['adj_factor']],'traded_days':len(traded)})
 summaries={}
 for n in HORIZONS:
  raw_pairs=[r for r in rows if all(r['windows'][str(n)][side]['stock_pct'] is not None for side in ('before','after'))]
  paired=[r for r in raw_pairs if all(r['windows'][str(n)][side]['quote_endpoint_supported'] for side in ('before','after'))]
  ids={r['symbol'] for r in paired}
  def statistics(side):
   values=[r['windows'][str(n)][side] for r in paired]
   return {'count':len(values),'positive_count':sum(w['stock_pct']>0 for w in values),'negative_count':sum(w['stock_pct']<0 for w in values),'flat_count':sum(w['stock_pct']==0 for w in values),'mean_pct':mean(w['stock_pct'] for w in values) if values else None,'median_pct':median(w['stock_pct'] for w in values) if values else None,'beat_market_count':sum(w['market_excess_pp']>0 for w in values),'beat_st_count':sum(w['st_excess_pp']>0 for w in values),'mean_market_pct':mean(w['market_pct'] for w in values) if values else None,'mean_st_pct':mean(w['st_pct'] for w in values) if values else None}
  patterns=Counter()
  for r in paired:
   b=r['windows'][str(n)]['before']['stock_pct'];a=r['windows'][str(n)]['after']['stock_pct'];patterns['positive_to_negative' if b>0>a else 'negative_to_positive' if b<0<a else 'both_positive' if b>0 and a>0 else 'both_negative' if b<0 and a<0 else 'flat_involved']+=1
  date_sets={r['symbol']:{d for d in cal if r['windows'][str(n)]['after']['anchor']<d<=r['windows'][str(n)]['after']['through']} for r in paired};overlaps=[len(date_sets[a['symbol']]&date_sets[b['symbol']]) for a,b in combinations(paired,2)]
  groups={}
  for r in paired:
   key=r['pre_halt_close_on'];groups.setdefault(key,[]).append(r['symbol'])
  summaries[str(n)]={'days':n,'cohort_total':len(rows),'raw_pairable_count':len(raw_pairs),'paired_count':len(paired),'paired_symbols':sorted(ids),'not_paired':[{'symbol':r['symbol'],'name':r['name'],'before_status':r['windows'][str(n)]['before']['status'],'after_status':r['windows'][str(n)]['after']['status'],'quote_endpoints_supported':all(r['windows'][str(n)][side]['quote_endpoint_supported'] for side in ('before','after'))} for r in rows if r['symbol'] not in ids],'before':statistics('before'),'after':statistics('after'),'patterns':dict(patterns),'date_groups':[{'anchor':a,'symbols':s} for a,s in sorted(groups.items())],'date_group_count':len(groups),'overlapping_stock_pairs':sum(n>0 for n in overlaps),'possible_stock_pairs':len(overlaps),'max_overlap_days':max(overlaps,default=0)}
 default=summaries['20'];a=default['after']
 return {'through':end,'anchor':'2026-07-03','cohort_total':len(rows),'original_exit_total':transition['total'],'excluded':excluded,'rows':rows,'summaries':summaries,'default_days':20,'answer':f"摘帽后不是同一条路。{len(rows)}只撤销警示股票中，{default['paired_count']}只已有完整且端点报价相符的前后20市场日：后窗{a['positive_count']}涨、{a['negative_count']}跌，只有{a['beat_st_count']}只跑赢同期ST参考；其余样本保留为未完成观察，不把京蓝一例推广为普遍规律。",'quote_summary':{'valid_responses':len(source_refs),'new_responses':sum(not s.get('reused',False) for s in source_refs),'reused_responses':sum(s.get('reused',False) for s in source_refs),'quote_points':sum(c['points'] for r in rows for c in r['channels']),'actual_traded_security_days':sum(r['traded_days'] for r in rows),'raw_agree_companies':sum(r['all_original_raw_prices_agree'] for r in rows),'qfq_agree_companies':sum(r['all_qfq_prices_agree'] for r in rows),'qfq_difference_points':sum(len(c['price_differences']) for r in rows for c in r['channels'] if c['key']=='tencent_qfq'),'conflict_symbols':[r['symbol'] for r in rows if not r['all_qfq_prices_agree']],'failed_requests':p['failed_requests']},'what_would_change':'尚未满窗的样本走完后重新纳入同一口径；复权差异核清后再认证受影响窗口。关键财报、诉讼与履约若改变，分别更新公司判断，不用组均值替代个股。','boundary':'这是固定7月3日样本中、观察期内已撤销警示的事后分组，不是全体ST摘帽成功率。前后比较只用同一可配对公司，均值为各股异日同窗收益的简单平均，不是共同日期可交易组合。日期重叠和相同市场环境不作独立实验；超额只作百分点差，不是公告净贡献或已扣除风险后的独立收益。腾讯原始/前复权为同一报价渠道两种口径，不认证底层供数完全独立。原数据和未核复权差异不覆盖，无方法晋级。'}
