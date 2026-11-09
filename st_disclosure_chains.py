"""Curated document/fact/disclosure-day relations without erasing old evidence."""
from collections import defaultdict
from itertools import combinations
from hashlib import sha256
from canonical_json import digest
KEYS=('calendar','through','fixed_prices')
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def ann_digest(ann):return digest({k:ann[k]for k in ('verified_events','verified_documents','raw_fact_records','deduplicated_event_count')})
def disclosure_chain_view(i,ann):
 p=i.get('disclosure_chains')
 if p is None:return None
 if p['version']!=1 or p['through']!=i['through']or p['scope_digest']!=scope_digest(i)or p['announcement_digest']!=ann_digest(ann)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('disclosure relation source binding changed')
 if p['new_downloads']!=0 or p['method_promotions']!=0 or len(p['cases'])!=3 or {c['symbol']for c in p['cases']}!={'002667','600491','603398'}:raise ValueError('curated disclosure case scope changed')
 events={e['id']:e for e in ann['verified_events']};sources={s['announcement_id']:s for s in p['sources']}
 if len(sources)!=13 or len(p['sources'])!=13:raise ValueError('selected disclosure source set changed')
 for s in sources.values():
  if not s['protected_gate_passed']or len(s['page_text_hashes'])!=s['pages']or len(s['sha256'])!=64:raise ValueError('source replay certificate incomplete')
 for q in p['excerpts']:
  s=sources[q['announcement_id']]
  if q['page']<1 or q['page']>s['pages']or q['quote_digest']!=sha256(q['quote'].encode()).hexdigest():raise ValueError('source excerpt binding changed')
 selected=[];cases=[];cal=i['calendar'];prices={(r['symbol'],r['trade_date']):r for r in i['fixed_prices']}
 for c in p['cases']:
  groups=defaultdict(list);nodes=[];case_sources=set()
  for n in c['nodes']:
   e=events[n['event_id']]
   if e['symbol']!=c['symbol']or e['published_on']>i['through']:raise ValueError('relation crosses issuer or cutoff')
   refs=[]
   for s in [e['source'],*(e.get('supporting_sources')or[])]:
    bound=sources[s['announcement_id']]
    if s['sha256']!=bound['sha256']or s['page']<1 or s['page']>bound['pages']:raise ValueError('fact source ref changed')
    if not any(x['sha256']==s['sha256']and x['page']==s['page']for x in refs):refs.append(s)
    case_sources.add(s['sha256'])
   node={**n,'event':e,'sources':refs};nodes.append(node);selected.append(e['id']);groups[e['published_on']].append(node)
  if [n['event']['published_on']for n in nodes]!=sorted(n['event']['published_on']for n in nodes):raise ValueError('curated chain reverses known time')
  batches=[]
  for day,ns in sorted(groups.items()):
   observations=[n['event']['observation']for n in ns]
   if len({digest(x)for x in observations})!=1:raise ValueError('same-day observations disagree; cannot choose one')
   observation=observations[0];a=observation['anchor'];states={}
   for key,w in observation['windows'].items():
    endpoints=[prices.get((c['symbol'],d))for d in (a,w['through'])]
    states[key]='unfilled_followup'if not w['through']else'nontraded_or_missing_endpoint'if not all(r and r.get('has_trade')is True for r in endpoints)else'traded_endpoints'
   batches.append({'batch_id':c['symbol']+'-'+day,'published_on':day,'fact_count':len(ns),'nodes':ns,'observation':observation,'endpoint_states':states,'known_intraday_order':False})
  overlap={}
  for key in ('1','5','20'):
   valid=[b for b in batches if b['observation']['windows'][key]['stock_pct']is not None];pairs=[]
   for a,b in combinations(valid,2):
    dates=lambda z:{d for d in cal if z['observation']['anchor']<d<=z['observation']['windows'][key]['through']};shared=dates(a)&dates(b)
    if shared:pairs.append({'a':a['published_on'],'b':b['published_on'],'shared_market_days':len(shared)})
   overlap[key]={'eligible_observations':len(valid),'overlap_pairs':pairs,'overlap_pair_count':len(pairs)}
  cases.append({**c,'nodes':nodes,'batches':batches,'documents':len(case_sources),'fact_records':len(nodes),'disclosure_days':len(batches),'overlap':overlap})
 if len(selected)!=12 or len(set(selected))!=12:raise ValueError('fact views were duplicated or erased')
 # Known complementary facts must survive, while their identical date observation is counted once.
 wl=next(c for c in cases if c['symbol']=='002667');same=next(b for b in wl['batches']if b['published_on']=='2026-10-12')
 if {n['event_id']for n in same['nodes']}!={'tungsten_wl_offercompleted','weiling_offer_result_resume'}or same['fact_count']!=2:raise ValueError('result and transfer facts were incorrectly merged')
 for symbol,event_id,relation in [('002667','tungsten_wl_actualcontrol','later_related_control'),('600491','longyuan_completion_1225541847','new_completion_evidence'),('603398','asset_auction_fail','repeated_attempt_result')]:
  node=next(n for c in cases if c['symbol']==symbol for n in c['nodes']if n['event_id']==event_id)
  if node['relation']!=relation:raise ValueError('distinct program stage was conflated')
 return {'through':i['through'],'cases':cases,'selected_company_chains':3,'selected_fact_records':12,'selected_source_documents':len(sources),'selected_disclosure_days':sum(c['disclosure_days']for c in cases),'same_day_extra_fact_records':sum(c['fact_records']-c['disclosure_days']for c in cases),'excerpts':p['excerpts'],'source_replay':p['sources'],'new_downloads':0,'method_promotions':0,'prior_snapshot_digest':p['prior_snapshot_digest'],'boundary':p['boundary']}
