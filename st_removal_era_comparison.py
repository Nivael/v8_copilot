"""Comparable removal-event windows; expose crossing regimes and unequal follow-up."""
from decimal import Decimal as D,ROUND_HALF_UP
from statistics import mean,median
from math import prod,isclose
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source
from st_pre_rule_membership import pre_rule_membership_view
from st_member_transitions import member_transition_view
from st_juewei_adjustment import juewei_adjustment_view,reconstruction_support
HORIZONS=(5,20,40)
KEYS=('calendar','through','pre_rule_membership','member_transitions','dynamic_reference_audit','juewei_adjustment')
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def stats(rows):
 vals=[w['stock_pct']for w in rows];return {'count':len(rows),'positive':sum(v>0 for v in vals),'negative':sum(v<0 for v in vals),'flat':sum(v==0 for v in vals),'median_pct':median(vals)if vals else None,'mean_pct':mean(vals)if vals else None,'market_mean_pct':mean(w['market_pct']for w in rows)if rows else None,'st_mean_pct':mean(w['st_pct']for w in rows)if rows else None,'market_excess_median_pp':median(w['market_excess_pp']for w in rows)if rows else None,'st_excess_median_pp':median(w['st_excess_pp']for w in rows)if rows else None,'beat_market':sum(w['market_excess_pp']>0 for w in rows),'beat_st':sum(w['st_excess_pp']>0 for w in rows),'cross_rule':sum(w['cross_rule']for w in rows),'negative_market':sum(w['market_pct']<0 for w in rows),'negative_st':sum(w['st_pct']<0 for w in rows),'min_pct':min(vals)if vals else None,'max_pct':max(vals)if vals else None}
def removal_era_comparison(i,daily):
 p=i.get('removal_era_comparison')
 if p is None:return None
 if p['scope_digest']!=scope_digest(i)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'})or p['version']!=1 or p['new_network_queries']!=0 or p['horizons']!=list(HORIZONS)or p['rule_day']!='2026-07-06':raise ValueError('removal-era scope changed')
 pre=[r for r in pre_rule_membership_view(i)['rows']if r['kind']=='warning_removed'];post=[r for r in member_transition_view(i)['rows']if r['status']=='warning_removed'];targets=[('pre',r)for r in pre]+[('post',r)for r in post];symbols={r['symbol']for _,r in targets}
 if len(pre)!=37 or len(post)!=12 or len(symbols)!=49:raise ValueError('removal-era event scope changed')
 cal=i['calendar'];companies={c['symbol']:c for c in i['dynamic_reference_audit']['original_prices']['companies']};source_refs=[s for s in i['dynamic_reference_audit']['sources']if s['symbol']in symbols];quotes={(s['symbol'],s['key']):quotes_from_source(s)for s in source_refs}
 if len(quotes)!=98:raise ValueError('removal-era quote coverage changed')
 daily_by={r['date']:r for r in daily};rows=[];adjustment=juewei_adjustment_view(i)
 for era,t in targets:
  symbol=t['symbol'];company=companies[symbol];base={r['date']:r for r in company['rows']}
  if list(base)!=cal:raise ValueError('removal-era price calendar changed')
  if any(r['has_trade']!=bool(r['volume']is not None and r['volume']>0)for r in base.values()):raise ValueError('removal-era actual-trade flag changed')
  positive_factors=[r['adj_factor']for r in company['rows']if r['adj_factor']and r['adj_factor']>0]
  if len(positive_factors)!=len(cal):raise ValueError('removal-era factor history missing')
  factor=positive_factors[-1];effective=t['effective_on'];before=[d for d in cal if d<effective and base[d]['has_trade']];after=[d for d in cal if d>=effective and base[d]['has_trade']];anchor=before[-1]if before else None;resume=after[0]if after else None
  if resume!=effective:raise ValueError('removal-era resume differs from announcement')
  def qfq(r):return D(str(r['raw_close']))*D(str(r['adj_factor']))/D(str(factor))
  def window(a,b,n):
   result={'anchor':a,'through':b,'requested_days':n,'available_market_days':len([d for d in cal if a and d>a]),'status':'insufficient_history'if a is None else'insufficient_followup'if b is None else'nontraded_or_missing_endpoint','stock_pct':None,'market_pct':None,'st_pct':None,'market_excess_pp':None,'st_excess_pp':None,'cross_rule':bool(a and b and a<p['rule_day']<=b),'wholly_before_rule':bool(b and b<p['rule_day']),'nontrade_dates':[],'support_kind':'not_supported','raw_endpoints_agree':False,'direct_qfq_endpoints_agree':False,'factor_change_dates':[],'parallel_qfq_pct':None,'parallel_difference_pp':None,'factor_basis_supported':False}
   if not a or not b:return result
   dates=[d for d in cal if a<d<=b];ds=[daily_by[d]for d in dates]
   if n is not None and len(dates)!=n:raise ValueError('removal-era shortened calendar window')
   result.update(market_days=len(dates),available_market_days=len(dates),nontrade_dates=[d for d in dates if not base[d]['has_trade']],market_pct=(prod(1+d['market_pct']/100 for d in ds)-1)*100,st_pct=(prod(1+d['return_pct']/100 for d in ds)-1)*100)
   x,y=base[a],base[b]
   if not all(r['has_trade']and r['raw_close']is not None and r['raw_close']>0 for r in (x,y)):return result
   raw=quotes[(symbol,'tencent_raw')];q=quotes[(symbol,'tencent_qfq')];raw_agree=all(d in raw and raw[d]==D(str(base[d]['raw_close'])).quantize(D('.01'),rounding=ROUND_HALF_UP)for d in (a,b));qagree=all(d in q and q[d]==qfq(base[d]).quantize(D('.01'),rounding=ROUND_HALF_UP)for d in (a,b));span=[d for d in cal if a<=d<=b];changes=[d for j,d in enumerate(span)if j and base[d]['adj_factor']!=base[span[j-1]]['adj_factor']];value=float((qfq(y)/qfq(x)-1)*100);parallel=float((q[b]/q[a]-1)*100)if a in q and b in q and q[a]>0 else None;rebuilt=raw_agree and reconstruction_support(symbol,{'anchor':a,'through':b,'stock_pct':value,'status':'valid'},adjustment);supported=raw_agree and(qagree or not changes or rebuilt)
   result.update(status='valid'if supported else'factor_basis_unresolved',stock_pct=value,market_excess_pp=value-result['market_pct'],st_excess_pp=value-result['st_pct'],raw_endpoints_agree=raw_agree,direct_qfq_endpoints_agree=qagree,factor_change_dates=changes,parallel_qfq_pct=parallel,parallel_difference_pp=parallel-value if parallel is not None else None,factor_basis_supported=supported,support_kind='direct_qfq_endpoint_match'if raw_agree and qagree else'constant_factor_raw_ratio'if raw_agree and not changes else'verified_action_factor_reconstruction'if rebuilt else'not_supported')
   return result
  windows={}
  for n in HORIZONS:
   j=cal.index(anchor)if anchor else None;k=cal.index(resume);windows[str(n)]={'before':window(cal[j-n]if j is not None and j>=n else None,anchor,n),'including_resume':window(anchor,cal[j+n]if j is not None and j+n<len(cal)else None,n),'from_resume_close':window(resume,cal[k+n]if k+n<len(cal)else None,n)}
  first=window(anchor,resume,None);row={'era':era,'symbol':symbol,'name':t['name']if era=='pre'else t['new_name'],'effective_on':effective,'announced_on':t['metadata_published_on']if era=='pre'else t['announced_on'],'pre_halt_close_on':anchor,'resume_close_on':resume,'halt_dates':[d for d in cal if anchor and anchor<d<resume],'first_resume':first,'windows':windows,'official_body':t['verification_level']=='official_body'if era=='pre'else True,'source':next(s for s in i['pre_rule_membership']['sources']if s['announcement_id']==t['source_id'])if era=='pre'else t['facts'][0]['source']}
  row['source']={k:v for k,v in row['source'].items()if k in ('url','title','sha256','announcement_id','published_on','page','host_is_official')};rows.append(row)
 summaries={}
 for n in HORIZONS:
  groups={}
  for era,total in [('pre',37),('post',12)]:
   rs=[r for r in rows if r['era']==era];k=str(n);group={}
   for mode in ('including_resume','from_resume_close'):
    valid=[r for r in rs if r['windows'][k][mode]['status']=='valid'];paired=[r for r in valid if r['windows'][k]['before']['status']=='valid'];supported=lambda rr:[r['windows'][k][mode]for r in rr];pure=[r for r in valid if era=='post'or r['windows'][k][mode]['wholly_before_rule']];official=[r for r in valid if r['official_body']];conditions={}
    for label,predicate in [('market_down',lambda w:w['market_pct']<0),('market_up',lambda w:w['market_pct']>0)]:conditions[label]=stats([w for w in supported(valid)if predicate(w)])
    group[mode]={'total':total,'eligible_symbols':[r['symbol']for r in valid],'missing':[{'symbol':r['symbol'],'reason':r['windows'][k][mode]['status']}for r in rs if r not in valid],'all':stats(supported(valid)),'pure_regime':stats(supported(pure)),'pure_symbols':[r['symbol']for r in pure],'official_only':stats(supported(official)),'paired_count':len(paired),'paired_before':stats([r['windows'][k]['before']for r in paired]),'paired_after':stats(supported(paired)),'before_missing':[{'symbol':r['symbol'],'reason':r['windows'][k]['before']['status']if r['windows'][k]['before']['status']!='valid'else'after_'+r['windows'][k][mode]['status']}for r in rs if r not in paired],'first_up_total':sum(r['first_resume']['status']=='valid'and r['first_resume']['stock_pct']>0 for r in valid),'first_up_then_down':sum(r['first_resume']['status']=='valid'and r['first_resume']['stock_pct']>0 and r['windows'][k][mode]['stock_pct']<0 for r in valid),'first_up_and_after_up':sum(r['first_resume']['status']=='valid'and r['first_resume']['stock_pct']>0 and r['windows'][k][mode]['stock_pct']>0 for r in valid),'market_conditions':conditions}
   groups[era]=group
  summaries[str(n)]=groups
 first_summary={era:stats([r['first_resume']for r in rows if r['era']==era and r['first_resume']['status']=='valid'])for era in ('pre','post')};main=summaries['20'];a=main['pre']['from_resume_close']['all'];b=main['post']['from_resume_close']['all'];return {'through':i['through'],'rule_day':p['rule_day'],'total':49,'pre_count':37,'post_count':12,'default_days':20,'rows':rows,'summaries':summaries,'first_resume':first_summary,'quote_sources':[{'symbol':s['symbol'],'key':s['key'],'url':s['url'],'sha256':s['sha256'],'observed_at':s['observed_at'],'reused':True}for s in source_refs],'answer':f'摘帽首日与随后走势要分开。复牌收盘后20市场日，制度前事件组{a["count"]}只可核、{a["positive"]}涨{a["negative"]}跌；制度后组{b["count"]}只可核、{b["positive"]}涨{b["negative"]}跌，另{12-b["count"]}只后窗未满或口径待核。前组{a["cross_rule"]}个窗口跨过7月6日，不能将组间差异说成旧新制度的净影响。','boundary':'37与12均为本研究观察范围内事后识别的撤销事件，不是所有ST的摘帽成功率或随机对照。前组来自5月6日在册且7月3日前移出的37家，后组来自7月3日固定150中的12家，名单选择与时期不同。窗口收益为异日个股简单统计，不是同日可交易组合。大盘/ST差值不是风险调整后的独立收益或公告净贡献；窗口重叠、同涨跌市场下分组也不构成独立试验。五份镜像与官方原件分层，未满窗口和缺前史不填零、不缩窗。常因子原始价比与直接前复权仅为同一价格区间的可核构造；公司行动因子变动且直接端点不一致时保留待核，不沿用其他公司的解释。没有通用经验晋级。'}
