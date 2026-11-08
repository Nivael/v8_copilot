"""Source-bound halt mechanisms; verified stages never imply unobserved outcomes."""
from canonical_json import digest
from decimal import Decimal

def scope_digest(i):return digest({k:i[k] for k in ('calendar','through','fixed_prices','activities')})
def offer_result_view(result,i,acts,prices):
 if result is None:return None
 if result['result_on']>i['through'] or result['halt_on'] not in i['calendar'] or result['resume_on'] not in i['calendar'] or not(result['halt_on']<result['resume_on']):raise ValueError('invalid offer result timeline')
 planned=result['planned_shares'];accepted=result['accepted_shares'];price=Decimal(result['price_per_share'])
 if type(planned) is not int or type(accepted) is not int or not(0<accepted<=planned) or price<=0:raise ValueError('invalid offer result quantity')
 if result['settlement_status'] not in ('arranged_not_confirmed','confirmed_complete'):raise ValueError('unknown settlement stage')
 if result['settlement_status']=='confirmed_complete' and not result.get('completion_receipt'):raise ValueError('settlement completion lacks receipt')
 for f in result['facts']:
  if f['published_on']>i['through'] or not all(f['source'].get(k) for k in ('sha256','url','page','title')):raise ValueError('offer result lacks timely source')
 dates=[d for d in i['calendar'] if result['halt_on']<=d<result['resume_on']];a=[acts.get(('600491',d)) for d in dates];r=prices.get(('600491',result['resume_on']))
 return {**result,'planned_consideration':str((price*planned).quantize(Decimal('.01'))),'accepted_price_consideration':str((price*accepted).quantize(Decimal('.01'))),'accepted_to_planned_pct':float(Decimal(accepted)/planned*100),'halt_market_days':len(dates),'halt_dates':dates,'all_halt_days_confirmed':all(x and x['suspension_status']=='suspended' and not(x.get('volume') and x['volume']>0) for x in a),'resume_has_trade':r.get('has_trade') if r else None}

def halt_stage_view(i):
 p=i.get('halt_stages')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items() if k!='content_digest'}) or p['scope_digest']!=scope_digest(i):raise ValueError('halt stage source or price scope changed')
 if len(p['rows'])!=2 or {r['symbol'] for r in p['rows']}!={'002717','600491'}:raise ValueError('halt stage subject scope changed')
 cal=i['calendar'];acts={(r['symbol'],r['trade_date']):r for r in i['activities']};prices={(r['symbol'],r['trade_date']):r for r in i['fixed_prices']};rows=[]
 for r in p['rows']:
  if r['halt_on'] not in cal or r.get('resume_on') and not(r['resume_on'] in cal and r['halt_on']<r['resume_on']<=i['through']):raise ValueError('invalid halt stage date')
  for f in r['facts']:
   if f['published_on']>i['through'] or not all(f['source'].get(k) for k in ('sha256','url','page','title')):raise ValueError('halt fact lacks timely source')
  stop=r['resume_on'] or i['through'];dates=[d for d in cal if r['halt_on']<=d and (d<stop if r['resume_on'] else d<=stop)];states=[acts.get((r['symbol'],d)) for d in dates];confirmed=all(x is not None and x['suspension_status']=='suspended' and not(x.get('volume') is not None and x['volume']>0) for x in states)
  prior=[d for d in cal if d<r['halt_on'] and (prices.get((r['symbol'],d)) or {}).get('has_trade') is True];last=prior[-1] if prior else None
  resume=prices.get((r['symbol'],r['resume_on'])) if r['resume_on'] else None
  rows.append({**r,'offer_result':offer_result_view(p.get('offer_results',{}).get(r['symbol']),i,acts,prices),'halt_market_days':len(dates),'halt_dates':dates,'all_halt_days_confirmed':confirmed,'last_pre_halt_trade':{'date':last,'close':prices[(r['symbol'],last)]['close']} if last else None,'resume_has_trade':resume.get('has_trade') if resume else None})
 return {'through':i['through'],'rows':rows,**p.get('refresh',{'new_primary_documents':2,'new_primary_pages':4,'reused_primary_documents':3,'reused_primary_pages':13}),'boundary':'只把已核原件阶段与共同日期成交状态串联。目录未检出不等于没有最终文件；停牌、事先告知、最终决定和摘牌分开。复牌也不代表收购完成、其他警示解除或可按停牌参考价成交；连续停牌日与重复节点不增加独立经验次数。'}
