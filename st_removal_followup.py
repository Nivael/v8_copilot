"""One warning-removal case: distinguish formal status, earnings, cash and execution."""
from decimal import Decimal as D
from math import prod
from canonical_json import digest
from st_halt_price_crosscheck import _scoped_price_check_view
from reported_financial_checks import compare_reported_figures,check_positive_base_change

def scope_digest(i):
 return digest({k:i[k] for k in ('calendar','through','fixed_prices','benchmarks','member_transitions')})

def removal_followup_view(i,daily):
 p=i.get('jinglan_followup')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('removal followup source/scope changed')
 if p['symbol']!='000711' or p['through']!=i['through']:raise ValueError('removal identity/cutoff changed')
 t=next(r for r in i['member_transitions']['rows'] if r['symbol']=='000711');w=p['warning']
 if t['effective_on']!=w['effective_on'] or t['suspend_on']!=w['suspend_on'] or not(w['application_published_on']<w['removal_published_on']<w['effective_on']) or w['application_approved_at_that_time'] is not False or w['exact_approval_on'] is not None or w['limit_after_pct']!=10:raise ValueError('application/removal boundary changed')
 h,q=p['reports']
 if (h['period_start'],h['period_end'],q['period_start'],q['period_end'])!=('2026-01-01','2026-06-30','2026-01-01','2026-09-30') or q['audited'] is not False:raise ValueError('financial periods/audit changed')
 for r in (h,q):
  if r['currency']!='CNY' or r['unit']!='yuan' or r['published_on']>i['through']:raise ValueError('financial unit/cutoff changed')
  for k in ('revenue','parent_profit','deducted_profit','operating_cash','parent_equity'):D(r[k])
 c=p['compensation'];a=p['auction'];r=p['recovery'];cash=p['cash_rollforward']
 if D(c['received_before_last_yuan'])+D(c['last_received_yuan'])!=D(c['total_received_yuan']) or c['status']!='fully_received' or c['current_year_profit_equal_receipts'] is not False or c['commitment_2026_met'] is not None:raise ValueError('compensation scope/receipt changed')
 if a['status']!='repriced_not_completed' or any(a[k] is not None for k in ('actual_receipts_yuan','actual_confirmed_loss_yuan')) or r['final_judgment'] is not None or r['received_confirmed_yuan'] is not None:raise ValueError('unproven execution/merits')
 if D(a['conditional_disposal_loss_yuan'])-D(a['previous_conditional_loss_yuan'])!=D(a['previous_start_yuan'])-D(a['new_start_yuan']):raise ValueError('conditional auction loss arithmetic changed')
 if sum(D(cash[k]) for k in ('operating_yuan','investing_yuan','financing_yuan','fx_yuan'))!=D(cash['change_yuan']) or D(cash['opening_yuan'])+D(cash['change_yuan'])!=D(cash['closing_yuan']):raise ValueError('cash rollforward changed')
 single={k:str(D(q[k])-D(h[k])) for k in ('revenue','parent_profit','deducted_profit','operating_cash')}
 if any(D(single[k])!=D(p['q3_reported_single'][k]) for k in ('revenue','parent_profit','deducted_profit')) or D(q['parent_profit'])-D(q['deducted_profit'])!=D(p['nonrecurring']['year_to_date_yuan']):raise ValueError('single-quarter/nonrecurring changed')
 for f in p['facts']:
  if f['published_on']>i['through'] or not all(f['source'].get(k) for k in ('url','sha256','page','title')):raise ValueError('followup fact lacks timely source')
 figures=[]
 for n,report in enumerate((h,q)):
  for k in ('revenue','parent_profit','deducted_profit','operating_cash','parent_equity'):
   figures.append({'id':f'report{n}_{k}','symbol':'000711.SZ','entity':p['legal_name'],'metric':k,'unit':'CNY_yuan','period_start':None if k=='parent_equity' else report['period_start'],'period_end':report['period_end'],'value':report[k],'source':{**{x:report['source'][x] for x in ('url','sha256','page')},'published_on':report['published_on']}})
  if report.get('previous_parent_equity'):
   figures.append({'id':f'report{n}_prior_equity','symbol':'000711.SZ','entity':p['legal_name'],'metric':'parent_equity','unit':'CNY_yuan','period_start':None,'period_end':'2025-12-31','value':report['previous_parent_equity'],'source':{**{x:report['source'][x] for x in ('url','sha256','page')},'published_on':report['published_on']}})
 financial_checks=compare_reported_figures(figures)
 positive_base_checks=[check_positive_base_change(x['revenue'],x['previous_revenue'],x['revenue_yoy_pct']) for x in (h,q)]
 quote_input={**i,'jinglan_quote_check':p['price_check']}
 quotes=_scoped_price_check_view(quote_input,daily,packet_key='jinglan_quote_check',subjects={'000711':'京蓝'},allow_partial=True,boundary='京蓝所获收盘和实际成交日期核对；腾讯原始/前复权是同一渠道两种口径。东方财富断开保留，不认证底层供数独立。原固定样本与退出后价格分开，不据价格证明摘帽因果。')
 row=quotes['rows'][0];base={x['date']:x for x in p['price_check']['original_prices']['companies'][0]['rows']};cal=i['calendar']
 if base[w['suspend_on']]['has_trade'] or not base[w['effective_on']]['has_trade']:raise ValueError('removal suspension differs from quotes')
 anchor=max(d for d in cal if d<w['suspend_on'] and base[d]['has_trade']);idx=cal.index(anchor)
 def window(a,b):
  ds=[x for x in daily if a<x['date']<=b];first=base[a];last=base[b];usable=first['has_trade'] and last['has_trade']
  return {'anchor':a,'through':b,'market_days':len(ds),'stock_traded_days':sum(base[x['date']]['has_trade'] for x in ds),'stock_pct':(last['qfq_close']/first['qfq_close']-1)*100 if usable else None,'market_pct':(prod(1+x['market_pct']/100 for x in ds)-1)*100,'st_pct':(prod(1+x['return_pct']/100 for x in ds)-1)*100}
 price_windows={'full':window('2026-07-03',i['through']),'before20':window(cal[idx-20],anchor),'after20':window(anchor,cal[idx+20]),'pre_halt_to_cutoff':window(anchor,i['through']),'first_resume_close_to_cutoff':window(w['effective_on'],i['through'])}
 return {**{k:v for k,v in p.items() if k not in ('content_digest','scope_digest','price_check')},'single_quarter':single,'financial_checks':financial_checks,'positive_base_checks':positive_base_checks,'quotes':quotes,'price_windows':price_windows,'new_event_windows':[e for e in row['events'] if e['event_id'] in p['event_ids']],'independent_company_count':1,'audit_note':'三季报明确未经审计；半年仅选核摘要，本轮不从“非标准意见不适用”推定已审计或未审计。'}
