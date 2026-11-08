"""Source-bound halt mechanisms; verified stages never imply unobserved outcomes."""
from canonical_json import digest

def scope_digest(i):return digest({k:i[k] for k in ('calendar','through','fixed_prices','activities')})
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
  rows.append({**r,'halt_market_days':len(dates),'halt_dates':dates,'all_halt_days_confirmed':confirmed,'last_pre_halt_trade':{'date':last,'close':prices[(r['symbol'],last)]['close']} if last else None,'resume_has_trade':resume.get('has_trade') if resume else None})
 return {'through':i['through'],'rows':rows,'new_primary_documents':2,'new_primary_pages':4,'reused_primary_documents':3,'reused_primary_pages':13,'boundary':'只把已核原件阶段与共同日期成交状态串联。目录未检出不等于没有最终文件；停牌、事先告知、最终决定和摘牌分开。复牌也不代表收购完成、其他警示解除或可按停牌参考价成交；连续停牌日与重复节点不增加独立经验次数。'}
