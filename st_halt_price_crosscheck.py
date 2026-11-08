"""Two halt cases: traded close/calendar checks and source-bound event windows."""
from decimal import Decimal,ROUND_HALF_UP
from math import prod
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source

SUBJECTS={'600491':'龙元','002717':'岭南'}
def scope_digest(i):return digest({k:i[k] for k in ('calendar','through','fixed_prices','activities','benchmarks')})
def _scoped_price_check_view(i,daily,*,packet_key,subjects,boundary,allow_partial=False,include_alternate_dates=False):
 p=i.get(packet_key)
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('halt quote source/scope changed')
 original=p['original_prices'];cal=i['calendar'];end=i['through']
 if original['calendar']!=cal or original['through']!=end or {r['symbol'] for r in original['companies']}!=set(subjects) or len(original['companies'])!=len(subjects):raise ValueError('halt quote subjects/calendar changed')
 output=[]
 for c in original['companies']:
  s=c['symbol'];base={r['date']:r for r in c['rows']}
  if [r['date'] for r in c['rows']]!=cal or c['qfq_normalization_date']!=end:raise ValueError('halt original calendar changed')
  for r in c['rows']:
   if r['has_trade']!=bool(r['volume'] is not None and r['volume']>0):raise ValueError('halt trade flag changed')
   expected=float(Decimal(str(r['raw_close']))*Decimal(str(r['adj_factor']))/Decimal(str(c['qfq_normalization_factor']))) if r['raw_close'] is not None and r['adj_factor'] else None
   if r['qfq_close']!=expected:raise ValueError('halt qfq calculation changed')
  traded={d for d,r in base.items() if r['has_trade']};channels=[];maps={};sources=[r for r in p['sources'] if r['symbol']==s]
  keys={r['key'] for r in sources};expected_keys={'tencent_raw','tencent_qfq','eastmoney_raw','eastmoney_qfq'}
  if len(keys)!=len(sources) or not keys<=expected_keys or (not allow_partial and keys!=expected_keys) or not keys:raise ValueError('halt quote channels incomplete')
  for source in sources:
   q=quotes_from_source(source);maps[source['key']]=q
   if set(q)-set(cal):raise ValueError('halt quote outside calendar')
   diffs=[]
   for d in sorted(set(q)&traded):
    a=Decimal(str(base[d]['qfq_close' if source['key'].endswith('qfq') else 'raw_close']));expected=a.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    if q[d]!=expected:diffs.append({'date':d,'original_close':str(a),'checked_close':str(q[d]),'difference':str(q[d]-a)})
   channels.append({'key':source['key'],'points':len(q),'matched_points':len(set(q)&traded)-len(diffs),'missing_trade_dates':sorted(traded-set(q)),'extra_nontrade_dates':sorted(set(q)-traded),'price_differences':diffs,'source':{k:source[k] for k in ('url','sha256','observed_at')}})
  events=[]
  def window(anchor,through):
   ds=[r for r in daily if anchor<r['date']<=through];a=base[anchor];b=base[through];usable=a['has_trade'] and b['has_trade'];value=(b['qfq_close']/a['qfq_close']-1)*100 if usable else None
   return {'anchor':anchor,'through':through,'market_days':len(ds),'stock_pct':value,'market_pct':(prod(1+r['market_pct']/100 for r in ds)-1)*100,'st_pct':(prod(1+r['return_pct']/100 for r in ds)-1)*100,'raw_reference_pct':(b['qfq_close']/a['qfq_close']-1)*100 if a['qfq_close'] and b['qfq_close'] else None,'anchor_traded':a['has_trade'],'end_traded':b['has_trade'],'checked_qfq_returns':{key:float((q[through]/q[anchor]-1)*100) if usable and anchor in q and through in q else None for key,q in maps.items() if key.endswith('qfq')}}
  for e in i['announcement_study']['verified_events']:
   if e['symbol']!=s:continue
   eligible=[d for d in cal if d<=e['published_on']];anchor=eligible[-1] if eligible else None;windows={}
   for n in (1,5,20):
    remaining=[d for d in cal if anchor and d>anchor];through=remaining[n-1] if len(remaining)>=n else None;windows[str(n)]=window(anchor,through) if anchor and through else None
   events.append({'event_id':e['id'],'title':e['title'],'published_on':e['published_on'],'background_only':anchor is None,'windows':windows})
   if include_alternate_dates and e.get('alternate_published_on'):
    alt=e['alternate_published_on'];aa=max((d for d in cal if d<=alt),default=None);remaining=[d for d in cal if aa and d>aa]
    events.append({'event_id':e['id']+'_alternate','title':e['title']+'（媒体日期敏感性）','published_on':alt,'background_only':aa is None,'windows':{str(n):window(aa,remaining[n-1]) if aa and len(remaining)>=n else None for n in (1,5,20)}})
  endpoint=window('2026-07-03',end);last=max(traded);actual_start='2026-07-03' if base['2026-07-03']['has_trade'] else max((d for d in traded if d<'2026-07-03'),default=None);alternative=window(actual_start,last) if actual_start and (actual_start!='2026-07-03' or last!=end) else None;last_period=window('2026-07-03',last) if base['2026-07-03']['has_trade'] and last!=end else None
  frozen=[r for r in i['fixed_prices'] if r['symbol']==s];conflicts=[r['trade_date'] for r in frozen if r.get('has_trade') is not base[r['trade_date']]['has_trade'] or r.get('has_trade') is True and Decimal(str(r['close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=Decimal(str(base[r['trade_date']]['qfq_close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)]
  output.append({'symbol':s,'name':subjects[s],'calendar_days':len(cal),'traded_days':len(traded),'all_available_prices_agree':keys==expected_keys and not conflicts and all(not r['price_differences'] and not r['missing_trade_dates'] and not r['extra_nontrade_dates'] for r in channels),'frozen_price_conflicts':conflicts,'channels':channels,'factor_change_dates':[r['date'] for n,r in enumerate(c['rows']) if n and r['adj_factor']!=c['rows'][n-1]['adj_factor']],'nontrade_dates':[{'date':r['date'],'has_reference_close':r['raw_close'] is not None,'provider_reports_suspension':any(x['suspend_type']=='S' for x in r['suspension_records'])} for r in c['rows'] if not r['has_trade']],'last_actual_close':{'date':last,'close':base[last]['raw_close']},'full_window':endpoint,'last_actual_period':last_period,'alternative_actual_period':alternative,'events':events})
 return {'through':end,'start':cal[0],'rows':output,'quote_points':sum(c['points'] for r in output for c in r['channels']),'unique_traded_security_days':sum(r['traded_days'] for r in output),'valid_responses':len(p['sources']),'resolved_retries':len(p['resolved_retries']),'failed_requests':p['failed_requests'],'all_available_prices_agree':all(r['all_available_prices_agree'] for r in output),'boundary':boundary}

def halt_price_check_view(i,daily):
 return _scoped_price_check_view(i,daily,packet_key='halt_price_crosscheck',subjects=SUBJECTS,boundary='只核龙元、岭南在本窗口实际成交日期的收盘及原始/前复权口径，不认证全体ST价格、开高低收全字段或底层供数独立。停牌共同端点不补零，最后成交日另窗不替换共同日期。原报价、旧窗口与公司程序不由此改写；行情一致不证明公告因果、资金过户或最终退市。来源链接可能更新，以本轮冻结原响应核对。')
