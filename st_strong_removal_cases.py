"""Read strong post-removal paths alongside dated financial facts, without hindsight causality."""
from decimal import Decimal as D
from math import prod
from canonical_json import digest

METRICS=('revenue','parent_profit','deducted_profit','operating_cash','parent_equity')
def scope_digest(i):
 return digest({k:i[k] for k in ('calendar','through','fixed_prices','benchmarks','member_transitions','removal_cohort')})

def strong_removal_cases_view(i,cohort,daily):
 p=i.get('strong_removal_cases')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('strong cases source/scope changed')
 if p['through']!=i['through'] or {r['symbol']for r in p['rows']}!={'000820','002199'} or len(p['rows'])!=2:raise ValueError('strong cases identity/cutoff changed')
 sources={r['sha256']:r for r in p['sources']}
 def source_check(s,day,symbol):
  original=sources.get(s['sha256'])
  if not original or original['symbol']!=symbol or original['published_on']!=day or original['url']!=s['url'] or not 1<=s['page']<=original['pages'] or s.get('page_text_hash')!=original['page_text_hashes'][s['page']-1] or day>i['through']:raise ValueError('strong case timely page/source changed')
 rows=[]
 for r in p['rows']:
  s=r['symbol'];c=next(x for x in cohort['rows']if x['symbol']==s);h,q=r['half'],r['third']
  if (h['period_end'],q['period_end'])!=('2026-06-30','2026-09-30') or q['audited']is not False or h['audited']is not None or not c['halt_and_resume_match']:raise ValueError('period/audit/stage changed')
  for report in (h,q):
   if report['currency']!='CNY' or report['unit']!='yuan' or report['period_start']!='2026-01-01' or report['published_on']<=c['effective_on']:raise ValueError('financial unit/known date changed')
   for k in METRICS:
    D(report[k]);source_check(report['metric_sources'][k],report['published_on'],s)
  single={k:str(D(q[k])-D(h[k]))for k in METRICS if k!='parent_equity'}
  if any(D(single[k])!=D(r['reported_q3_single'][k])for k in ('revenue','parent_profit','deducted_profit')):raise ValueError('single quarter does not reconcile')
  cash=r['cash'];source_check(cash['source'],q['published_on'],s);total=sum(D(cash[k])for k in ('operating','investing','financing','fx'))
  if D(cash['operating'])!=D(q['operating_cash']) or total!=D(cash['change']) or D(cash['opening'])+total!=D(cash['closing']):raise ValueError('cash rollforward does not reconcile')
  correction=r.get('correction')
  if correction:
   if not(c['effective_on']<correction['original']['published_on']<correction['published_on']==h['published_on']):raise ValueError('correction known date changed')
   for report in (correction['original'],):
    for k in METRICS:source_check(report['metric_sources'][k],report['published_on'],s)
   source_check(correction['source'],correction['published_on'],s)
   for k in ('parent_profit','operating_cash','parent_equity'):
    if correction['original'][k]!=h[k]:raise ValueError('unchanged corrected metric changed')
   if D(correction['original']['parent_profit'])-D(correction['original']['deducted_profit'])!=D(correction['old_nonrecurring']) or D(h['parent_profit'])-D(h['deducted_profit'])!=D(correction['new_nonrecurring']):raise ValueError('correction nonrecurring does not reconcile')
   correction={**correction,'delta':{k:str(D(h[k])-D(correction['original'][k]))for k in METRICS},'incorrect_q3_from_old_half':str(D(q['deducted_profit'])-D(correction['original']['deducted_profit']))}
  for f in r['facts']:source_check(f['source'],f['published_on'],s)
  original_half=r['correction']['original'] if r.get('correction')else h
  if min(original_half['published_on'],q['published_on'])<=c['windows']['5']['after']['through']:raise ValueError('later report cannot be claimed known after short window')
  windows=c['windows'];first=next(x for x in i['fixed_prices']if x['symbol']==s and x['trade_date']=='2026-07-03');last=next(x for x in i['fixed_prices']if x['symbol']==s and x['trade_date']==i['through']);ds=[x for x in daily if '2026-07-03'<x['date']<=i['through']]
  full={'anchor':'2026-07-03','through':i['through'],'market_days':len(ds),'stock_pct':(last['close']/first['close']-1)*100 if first['has_trade']and last['has_trade']else None,'market_pct':(prod(1+x['market_pct']/100 for x in ds)-1)*100,'st_pct':(prod(1+x['return_pct']/100 for x in ds)-1)*100}
  rows.append({**r,'correction':correction,'single_quarter':single,'nonrecurring_ytd':str(D(q['parent_profit'])-D(q['deducted_profit'])),'windows':windows,'full':full,'removal':{k:c[k]for k in ('announced_on','suspend_on','effective_on','facts')},'known_at_removal':{'half_actual_available':False,'q3_actual_available':False,'correction_available':False},'cash_check_passed':True})
 return {**{k:v for k,v in p.items()if k not in ('rows','content_digest','scope_digest')},'rows':rows,'cohort5':cohort['summaries']['5'],'selection':'从已摘帽组中按后5日强势路径选取两个案例，只用于检验解释边界，不是随机样本或预测检验。','boundary':'两个公司不同日期、窗口有重叠；财报发布日期晚于摘帽与短窗，不能将后来财报当成当时已知或上涨净因果。负利润、经营现金流、现金余额及调查状态分别判断。'}
