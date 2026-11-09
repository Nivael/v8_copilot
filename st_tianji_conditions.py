"""Dated earnings/cash improvement and a distinct false-statement warning route."""
from decimal import Decimal as D
from math import prod
from canonical_json import digest
from st_halt_price_crosscheck import _scoped_price_check_view
from reported_financial_checks import check_positive_base_change

def scope_digest(i):
 return digest({k:i[k]for k in ('calendar','through','fixed_prices','benchmarks','member_entries','member_transitions','jinglan_followup','strong_removal_cases','official_membership_audit')})

def tianji_conditions_view(i,daily):
 p=i.get('tianji_conditions')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('tianji comparison source/scope changed')
 if p['symbol']!='002759' or p['through']!=i['through']:raise ValueError('tianji identity/cutoff changed')
 sources={s['sha256']:s for s in p['sources']};rule=p['rule'];sources[rule['sha256']]=rule
 def check(s,day):
  r=sources.get(s['sha256'])
  if not r or r['published_on']!=day or r['url'].split('#')[0]!=s['url'].split('#')[0] or not 1<=s['page']<=r['pages'] or s['page_text_hash']!=r['page_text_hashes'][s['page']-1] or day>p['through']:raise ValueError('tianji timely page/source changed')
 for f in p['facts']:check(f['source'],f['published_on'])
 h,q=p['reports'];forecast=p['forecast'];w=p['warning'];entry=next(r for r in i['member_entries']['rows']if r['symbol']=='002759')
 for source,day in [(w['warning_source'],w['published_on']),(w['decision_source'],w['decision_published_on']),(w['restatement_source'],w['decision_published_on']),(w['conditions_source'],rule['published_on']),(w['application_source'],rule['published_on']),(forecast['source'],forecast['published_on'])]:check(source,day)
 if w['effective_on']!=entry['effective_on'] or w['suspend_on']!=entry['suspend_on'] or w['published_on']!=entry['announced_on'] or w['limit_after_pct']!=10 or w['rule_item']!='9.8.1(8)':raise ValueError('tianji warning boundary changed')
 if not(w['notice_received_on']<w['published_on']==forecast['published_on']<w['effective_on']<w['decision_received_on']<w['decision_published_on']<=h['published_on']<q['published_on']<=p['through']):raise ValueError('known dates or forecast/actual order changed')
 if w['decision_made_on']is not None or w['removal_estimated_on']is not None or w['approved_on']is not None or w['months_required']!=12 or w['clock_anchor']!='decision_made_on' or w['automatic_removal']is not False or w['decision_still_finds_misstatement']is not True or w['exception_supported']is not False:raise ValueError('unproven warning clock, approval or exception')
 if w['restatement_reported_done']is not True or w['restatement_independently_reaudited']is not False or forecast['audited']is not False or forecast['operating_cash_forecast']is not None:raise ValueError('restatement or forecast coverage changed')
 if (h['period_end'],q['period_end'])!=('2026-06-30','2026-09-30') or q['audited']is not False or h['audited']is not None:raise ValueError('report periods/audit changed')
 for report in (h,q):
  if report['period_start']!='2026-01-01' or report['unit']!='yuan' or report['currency']!='CNY':raise ValueError('financial metric scope changed')
  for k in ('revenue','parent_profit','deducted_profit','operating_cash','parent_equity'):D(report[k]);check(report['metric_sources'][k],report['published_on'])
 for k in ('parent_profit','deducted_profit'):
  if not D(forecast[k+'_low'])<=D(h[k])<=D(forecast[k+'_high']):raise ValueError('actual half differs from disclosed forecast range')
 single={k:str(D(q[k])-D(h[k]))for k in ('revenue','parent_profit','deducted_profit','operating_cash')}
 if any(D(single[k])!=D(p['reported_q3_single'][k])for k in ('revenue','parent_profit','deducted_profit')) or D(q['parent_profit'])-D(q['deducted_profit'])!=D(p['nonrecurring_ytd']):raise ValueError('single/nonrecurring reconciliation changed')
 cash=p['cash'];check(cash['source'],q['published_on']);check(cash['operating_source'],q['published_on'])
 if D(cash['operating'])!=D(q['operating_cash']) or sum(D(cash[k])for k in ('operating','investing','financing','fx'))!=D(cash['change']) or D(cash['opening'])+D(cash['change'])!=D(cash['closing']):raise ValueError('cash rollforward changed')
 for s in ('002759','603021','000711','000820','002199'):
  if not any(x['symbol']==s for x in i['fixed_prices']):raise ValueError('comparison price subject missing')
 hp=next(c for c in i['official_membership_audit']['issuer_checks']if c['symbol']=='603021')['followup']['reports'][-1];jl=i['jinglan_followup']['reports'][-1];others={r['symbol']:r['third']for r in i['strong_removal_cases']['rows']}
 choices=[('002759','ST天际',q,'7月15日新增其他风险警示；虚假记载事项及处罚时钟另核'),('000711','京蓝',jl,'8月31日撤销其他风险警示；经营现金与履约另核'),('603021','*ST华鹏',hp,'负归母净资产相关退市风险警示；各子公司账户另核'),('000820','神雾节能',others['000820'],'7月30日撤销退市风险警示；当期亏损与现金另核'),('002199','东晶电子',others['002199'],'7月23日撤销退市风险警示；当期亏损与更正另核')]
 cal=i['calendar'];rows=[]
 def window(s,a,b):
  prices={r['trade_date']:r for r in i['fixed_prices']if r['symbol']==s};first,last=prices.get(a),prices.get(b);ds=[r for r in daily if a<r['date']<=b];usable=bool(first and last and first['has_trade']and last['has_trade'])
  return {'anchor':a,'through':b,'market_days':len(ds),'stock_traded_days':sum(bool(prices.get(r['date'],{}).get('has_trade'))for r in ds),'stock_pct':(last['close']/first['close']-1)*100 if usable else None,'market_pct':(prod(1+r['market_pct']/100 for r in ds)-1)*100,'st_pct':(prod(1+r['return_pct']/100 for r in ds)-1)*100}
 for s,name,r,cause in choices:
  if (r['period_start'],r['period_end'],r['currency'],r['unit'],r['audited'])!=('2026-01-01','2026-09-30','CNY','yuan',False) or r['published_on']>p['through']:raise ValueError('comparison period/unit/audit not same')
  metrics={k:r[k]for k in ('revenue','parent_profit','operating_cash','parent_equity')};metric_sources=r.get('metric_sources')or{k:r.get('equity_source',r['source'])if k=='parent_equity'else r['source']for k in metrics}
  rows.append({'symbol':s,'name':name,'warning_scope':cause,'financial':{**metrics,'published_on':r['published_on'],'period_start':r['period_start'],'period_end':r['period_end'],'audited':r['audited'],'metric_sources':metric_sources},'combination':'profit_'+('positive'if D(r['parent_profit'])>0 else'negative'if D(r['parent_profit'])<0 else'zero')+'_cash_'+('positive'if D(r['operating_cash'])>0 else'negative'if D(r['operating_cash'])<0 else'zero'),'windows':{'full':window(s,'2026-07-03',p['through']),'20':window(s,cal[-21],p['through']),'5':window(s,cal[-6],p['through'])}})
 quote_i={**i,'tianji_price_check':p['price_check']};quotes=_scoped_price_check_view(quote_i,daily,packet_key='tianji_price_check',subjects={'002759':'天际'},allow_partial=True,boundary='腾讯原价/前复权是同一核对渠道的两种口径，与原提供商冻结缓存比较；不把两条请求说成两家独立渠道，不认证底层供数独立。原150固定样本和12只摘帽组不改。')
 obtained_agree=all(not r['frozen_price_conflicts']and all(not c['price_differences']and not c['missing_trade_dates']and not c['extra_nontrade_dates']for c in r['channels'])for r in quotes['rows'])
 return {**{k:v for k,v in p.items()if k not in ('content_digest','scope_digest','price_check')},'single_quarter':single,'comparison':rows,'quote_check':quotes,'obtained_quotes_agree':obtained_agree,'positive_revenue_base_checks':[check_positive_base_change(r['revenue'],r['previous_revenue'],r['revenue_yoy_pct'])for r in (h,q)],'independent_companies':5,'events':[],'selection':'五家公司按利润/现金不同组合有目的选取，只有同一报告期及共同市场窗口；不是随机样本、全ST胜率或五次独立市场实验。天际7月15日才入ST，完整价格窗含此前非ST阶段，不补入7月3日固定150或12只摘帽组。'}
