"""Explain a frozen additive/factor price-basis difference without replacing either series."""
from decimal import Decimal as D,ROUND_HALF_UP,localcontext
from math import isclose
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

def scope_digest(i):
 return digest({k:i[k] for k in ('calendar','through','fixed_prices','benchmarks','removal_cohort')})

def juewei_adjustment_view(i):
 p=i.get('juewei_adjustment')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('Juewei adjustment source/scope changed')
 if p['symbol']!='603517' or p['through']!=i['through']:raise ValueError('Juewei identity/cutoff changed')
 action=p['action'];cal=i['calendar'];ex=action['ex_date'];previous=cal[cal.index(ex)-1]
 if action['record_date']!=previous or action['published_on']>action['record_date'] or action['scheduled_payment_on']!=ex or action['actual_personal_receipt_verified'] is not False or action['share_change_ratio']!='0':raise ValueError('dividend schedule/receipt scope changed')
 if not p['facts'] or {r['announcement_id'] for r in p['sources']}!={'1225610029','1225610010','1225610007'} or len(p['sources'])!=3:raise ValueError('dividend primary package incomplete')
 for f in p['facts']:
  matches=[r for r in p['sources'] if r['sha256']==f['source']['sha256'] and r['announcement_id']==f['source']['announcement_id']]
  if len(matches)!=1 or not 1<=f['source']['page']<=matches[0]['pages']:raise ValueError('dividend fact source/page changed')
  if f['published_on']>i['through'] or not all(f['source'].get(k) for k in ('sha256','page','title','url')):raise ValueError('adjustment fact lacks timely source')
 total=D(action['total_shares']);excluded=D(action['repurchase_shares']);eligible=D(action['eligible_shares']);cash=D(action['eligible_cash_per_share']);paid=D(action['scheduled_total_yuan']);reported=D(action['reported_rounded_reference_cash'])
 if total-excluded!=eligible or eligible*cash!=paid or total*cash!=D(action['prior_scheduled_total_yuan']):raise ValueError('dividend shares/total arithmetic changed')
 with localcontext() as ctx:
  ctx.prec=50;virtual=paid/total
 if virtual.quantize(D('.01'),rounding=ROUND_HALF_UP)!=reported:raise ValueError('declared reference rounding changed')
 packet=i['removal_cohort'];company=next(c for c in packet['original_prices']['companies'] if c['symbol']=='603517');base={r['date']:r for r in company['rows']};frozen={r['trade_date']:r for r in i['fixed_prices'] if r['symbol']=='603517'}
 traded={d for d,r in base.items() if r['has_trade']};raw=quotes_from_source(next(r for r in packet['sources'] if r['symbol']=='603517' and r['key']=='tencent_raw'));qfq=quotes_from_source(next(r for r in packet['sources'] if r['symbol']=='603517' and r['key']=='tencent_qfq'))
 raw_agree=set(raw)==traded and all(raw[d]==D(str(base[d]['raw_close'])) for d in traded)
 if set(qfq)!=traded:raise ValueError('adjusted quote dates changed')
 pre=D(str(base[previous]['raw_close']));close=D(str(base[ex]['raw_close']));reference=(pre-reported).quantize(D('.01'),rounding=ROUND_HALF_UP);rows=p['ex_date_cache_rows']
 provider_day=next(r['rows'][0] for r in rows if r['api']=='daily' and r['trade_date']==ex)
 if provider_day['ts_code']!='603517.SH' or D(str(provider_day['pre_close']))!=reference or D(str(provider_day['close']))!=close or provider_day['vol']<=0:raise ValueError('ex-date reference/cache conflict')
 before_factor=D(str(base[previous]['adj_factor']));on_factor=D(str(base[ex]['adj_factor']))
 factor_unrounded=before_factor*pre/reference;factor_rounded=factor_unrounded.quantize(D('.0001'),rounding=ROUND_HALF_UP);factor_agree=factor_rounded==on_factor and all(D(str(r['adj_factor']))==(before_factor if d<ex else on_factor) for d,r in base.items()) and D(str(company['qfq_normalization_factor']))==on_factor
 additive_mismatches=[];normalized={};normalized_mismatches=[];differences=[]
 for d in sorted(traded):
  additive=raw[d]-reported if d<ex else raw[d]
  if qfq[d]!=additive:additive_mismatches.append(d)
  # Same proportional basis rebuilt from independent raw closes and the formula-rounded factor.
  value=float(raw[d]*before_factor/factor_rounded) if d<ex else float(raw[d]);normalized[d]=value
  if not isclose(value,frozen[d]['close'],rel_tol=0,abs_tol=1e-12):normalized_mismatches.append(d)
  expected=D(str(base[d]['qfq_close'])).quantize(D('.01'),rounding=ROUND_HALF_UP)
  if qfq[d]!=expected:differences.append({'date':d,'factor_price':str(base[d]['qfq_close']),'additive_price':str(qfq[d]),'difference':str(qfq[d]-D(str(base[d]['qfq_close'])))})
 example=p['opinion_example'];example_price=D(example['raw_close']);actual_example=example_price-cash;virtual_example=example_price-virtual;example_actual_cent=actual_example.quantize(D('.01'),rounding=ROUND_HALF_UP);example_virtual_cent=virtual_example.quantize(D('.01'),rounding=ROUND_HALF_UP)
 if D(str(base[example['date']]['raw_close']))!=example_price or example_actual_cent!=D(example['reported_reference']) or example_virtual_cent!=D(example['reported_reference']):raise ValueError('opinion illustration/date changed')
 t=next(r for r in i['member_transitions']['rows'] if r['symbol']=='603517');anchor=max(d for d in traded if d<t['suspend_on']);idx=cal.index(anchor);examples={}
 for key,a,b in [('before',cal[idx-5],anchor),('after',anchor,cal[idx+5])]:
  examples[key]={'anchor':a,'through':b,'factor_pct':(frozen[b]['close']/frozen[a]['close']-1)*100,'additive_pct':float((qfq[b]/qfq[a]-1)*100),'normalized_pct':(normalized[b]/normalized[a]-1)*100}
 supported=raw_agree and factor_agree and not additive_mismatches and not normalized_mismatches
 return {**{k:v for k,v in p.items() if k not in ('content_digest','scope_digest','ex_date_cache_rows')},'status':'basis_reconstructed' if supported else 'unresolved','comparison_reconstruction_supported':supported,'raw_quote_agrees':raw_agree,'factor_matches_four_decimal_formula':factor_agree,'additive_mismatch_dates':additive_mismatches,'normalized_mismatch_dates':normalized_mismatches,'reconstructed_dates':len(normalized),'normalized_prices':normalized,'five_day_examples':examples,'direct_price_difference_count':len(differences),'direct_price_differences':differences,'calculation':{'virtual_cash_per_total_share':str(virtual),'reported_rounded_reference_cash':str(reported),'previous_session':previous,'previous_raw_close':str(pre),'ex_raw_close':str(close),'reference_before_rounding_virtual':str(pre-virtual),'reference_cent':str(reference),'raw_price_change_pct':float((close/pre-1)*100),'reference_change_pct':float((close/reference-1)*100),'factor_qfq_change_pct':float((D(str(base[ex]['qfq_close']))/D(str(base[previous]['qfq_close']))-1)*100),'additive_qfq_change_pct':float((qfq[ex]/qfq[previous]-1)*100),'factor_before':str(before_factor),'factor_on':str(on_factor),'formula_factor_before_rounding':str(factor_unrounded),'formula_factor_rounded':str(factor_rounded),'opinion_example_actual_cent':str(example_actual_cent),'opinion_example_virtual_cent':str(example_virtual_cent),'opinion_unrounded_reference_effect_pct':str(abs(actual_example-virtual_example)/actual_example*100)},'answer':(f"绝味的{len(differences)}日差异可以重建为两种价格构造，并非原始收盘冲突。冻结的腾讯前复权符合除息前原价减0.25元；面板沿用按因子比例缩放的口径。统一为同一因子法后，原始报价可支持原窗口读数，直接前复权数值差异仍保留。" if supported else '本轮重建有条件未满足，暂不能用归一结果认证窗口；原价格差异与来源保留待核。'),'boundary':'本轮仅解释该冻结序列与这次公司行动，不宣称取得腾讯通用算法规范或其他股票也适用。统一口径回算不是把两个原始前复权产品宣称相同。公告安排和参考价不证明任何个人实际到账、税后收益或可按复权价成交；除息不是新一项ST退出。'}

def reconstruction_support(symbol,window,adjustment):
 if symbol!='603517' or not adjustment or not adjustment['comparison_reconstruction_supported'] or window['status']!='valid':return False
 prices=adjustment['normalized_prices'];a=window['anchor'];b=window['through']
 if a not in prices or b not in prices:return False
 return isclose((prices[b]/prices[a]-1)*100,window['stock_pct'],rel_tol=0,abs_tol=1e-10)
