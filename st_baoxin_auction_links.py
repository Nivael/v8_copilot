"""Source-bound shareholder-lot matches; missing receipts are not failed transfers."""
from hashlib import sha256
from canonical_json import digest
KEYS=('calendar','through','fixed_prices')
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def ann_digest(ann):return digest({k:ann[k]for k in ('verified_events','verified_documents','raw_fact_records','deduplicated_event_count')})
REGISTERED={'bj-330':(3300000,'曹迅','K8156','北京市海淀区人民法院','2026-08-27','2026-11-02','2026-11-04','auction_august','ownership_nov'),'jm-400':(4000000,'杨静','G2213','江门市蓬江区人民法院','2026-08-29','2026-09-18','2026-09-23','auction_sept2','ownership_sept'),'st-612':(6120000,'吴栩涵','L4934','汕头市金平区人民法院','2026-09-11','2026-09-18','2026-09-23','auction_sept12','ownership_sept')}
REAUCTIONS={'hz-restricted':('首发后限售股','E4057','陈飞跃','P9195'),'hz-unrestricted':('无限售流通股','B9887','余芳琴','S2290')}
SELECTED={'jj-900':(9000000,'首发后限售股','靖江市人民法院'),'jj-230':(2300000,'无限售流通股','靖江市人民法院'),'jj-0501714':(501714,'无限售流通股','靖江市人民法院'),'hz-restricted':(5500000,'首发后限售股','杭州市拱墅区人民法院'),'hz-unrestricted':(5500000,'无限售流通股','杭州市拱墅区人民法院'),'hz-1460':(14600000,'首发后限售股','杭州市拱墅区人民法院'),'jj-424':(4240000,'首发后限售股','靖江市人民法院'),'aq-350':(3500000,'首发后限售股','安庆市宜秀区人民法院'),'bj-330':(3300000,'首发后限售股','北京市海淀区人民法院'),'jm-400':(4000000,'首发后限售股','江门市蓬江区人民法院'),'jj-942-group':(9420000,'首发后限售股','靖江市人民法院'),'ng-334':(3340000,'首发后限售股','宁国市人民法院'),'st-612':(6120000,'首发后限售股','汕头市金平区人民法院')}
def auction_links_view(i,ann):
 p=i.get('baoxin_auction_links')
 if p is None:return None
 if p['version']!=1 or p['symbol']!='002514'or p['through']!=i['through']or p['scope_digest']!=scope_digest(i)or p['announcement_digest']!=ann_digest(ann)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('Baoxin lot source binding changed')
 if p['new_downloads']!=0 or p['method_promotions']!=0:raise ValueError('lot review cannot promote methods or imply new coverage')
 sources={s['announcement_id']:s for s in p['sources']};pages={};events={e['id']:e for e in ann['verified_events']if e['symbol']=='002514'}
 if len(sources)!=10 or len(p['lots'])!=13 or len({r['lot_id']for r in p['lots']})!=13:raise ValueError('selected lot or source scope changed')
 for s in sources.values():
  if not s['protected_gate_passed']or len(s['page_text_hashes'])!=s['pages']:raise ValueError('frozen source replay missing')
 for q in p['evidence_pages']:
  s=sources[q['announcement_id']]
  if q['excerpt_digest']!=sha256(q['text'].encode()).hexdigest()or q['original_page_hash']!=s['page_text_hashes'][q['page']-1]:raise ValueError('lot identity evidence changed')
  pages[(q['announcement_id'],q['page'])]=q['text']
 for q in p['excerpts']:
  if q['quote_digest']!=sha256(q['quote'].encode()).hexdigest():raise ValueError('key lot excerpt changed')
 lots=[];used=set()
 for item in p['lots']:
  r={**item,'steps':[]};q=r['shares']
  if (q,r['share_type'],r['court'])!=SELECTED.get(r['lot_id']):raise ValueError('selected disclosure group identity changed')
  if not isinstance(q,int)or q<=0:raise ValueError('invalid share count')
  for x in item['steps']:
   s=x['source'];bound=sources[s['announcement_id']];e=events[x['event_id']];refs=sorted([s,*x.get('additional_sources',[])],key=lambda z:z['page'])
   if any(z['announcement_id']!=s['announcement_id']or z['sha256']!=bound['sha256']for z in refs):raise ValueError('cross-page proof crossed document identity')
   text=''.join(pages[(z['announcement_id'],z['page'])]for z in refs).replace(',','');alltext=''.join(t for (aid,_),t in pages.items()if aid==s['announcement_id']).replace(',','')
   if e['source']['sha256']!=s['sha256']or s['sha256']!=bound['sha256']or e['entity_scope']!='shareholder'and e['entity_scope']!='issuer':raise ValueError('lot evidence crossed source/subject')
   quantity_tokens=[str(q)]+([str(q//10000)+'万']if q%10000==0 else[])
   if not any(token in text for token in quantity_tokens)or r['court']not in alltext or '江苏立青'not in alltext:raise ValueError('share/court identity absent from cited source '+r['lot_id']+' '+s['announcement_id']+' '+str(s['page']))
   if x.get('buyer')and x['buyer']not in text or x.get('bid_id')and x['bid_id']not in text:raise ValueError('buyer/bid identity absent')
   if x.get('on'):
    y,m,d=x['on'].split('-');token=f'{int(m)}月{int(d)}日'
    if token not in alltext:raise ValueError('actual/scheduled/as-of date absent from source')
   r['steps'].append({**x,'published_on':e['published_on'],'source':{**bound,'page':s['page']},'source_refs':[{**bound,'page':z['page']}for z in refs]});used.add(e['id'])
  if item.get('allocations'):
   allocations=item['allocations'];alltext=''.join(pages[(s['announcement_id'],s['page'])]for s in item['allocation_sources']).replace(',','')
   if sum(a['shares']for a in allocations)!=q or len(allocations)!=11:raise ValueError('942 allocation total differs')
   for a in allocations:
    if not all(str(a[k])in alltext for k in ('buyer','bid_id','shares')):raise ValueError('allocation identity absent from original table')
  if r['status']=='registered':
   expected=REGISTERED.get(r['lot_id']);actual=(q,r['buyer'],r['steps'][0]['bid_id'],r['court'],r['auction_end'],r['registered_as_of'],r['registration_notice'],r['steps'][0]['event_id'],r['steps'][-1]['event_id'])
   if actual!=expected or r['steps'][-1].get('date_kind')!='as_of'or r['steps'][-1]['published_on']!=r['registration_notice']:raise ValueError('registration joined to the wrong auction')
  if r.get('matched_reauction'):
   expected=REAUCTIONS.get(r['lot_id']);actual=(r['share_type'],r['steps'][0]['bid_id'],r['steps'][-1]['buyer'],r['steps'][-1]['bid_id'])
   if actual!=expected or q!=5500000 or r['steps'][1].get('reauction_end')!='2026-09-01'or r['steps'][-1]['on']!='2026-09-01':raise ValueError('two share types or auction attempts were conflated')
  lots.append(r)
 if {r['lot_id']for r in lots if r['status']=='registered'}!=set(REGISTERED)or {r['lot_id']for r in lots if r.get('matched_reauction')}!=set(REAUCTIONS):raise ValueError('unearned completion or reauction match')
 c=p['known_conflicts'];text=pages[('1225424295',2)].replace(',','')
 if not all(str(c[k])in text for k in ('share_before','share_after_as_printed'))or c['two_lots_as_printed']!=[5500000,5500000]:raise ValueError('known July numeric conflict changed')
 printed_delta=c['share_before']-c['share_after_as_printed'];bid_total=sum(c['two_lots_as_printed'])
 if printed_delta!=9000000 or bid_total!=11000000:raise ValueError('known numeric conflict was silently repaired')
 first=events['second_fail_july']
 if first['published_on']!=c['july_published_on']or first.get('alternate_published_on')!=c['july_document_dated_on']:raise ValueError('known source-date conflict was hidden')
 gap=p['holding_gap']
 if str(gap['sept_after_as_printed'])not in pages[('1225577950',1)].replace(',','')or str(gap['nov_before_as_printed'])not in pages[('1225656282',1)].replace(',',''):raise ValueError('holding bridge lacks source values')
 gap={**gap,'unmatched_intermediate_change':gap['sept_after_as_printed']-gap['nov_before_as_printed']}
 observations=[events[eid]for eid in sorted(used,key=lambda eid:(events[eid]['published_on'],eid))]
 return {'through':i['through'],'lots':lots,'disclosure_groups':len(lots),'source_files':len(sources),'source_pages':sum(s['pages']for s in sources.values()),'registered_groups':3,'registered_shares':sum(r['shares']for r in lots if r['status']=='registered'),'reauction_groups':2,'reauction_underlying_shares':sum(r['shares']for r in lots if r.get('matched_reauction')),'registration_notice_days':len({r['registration_notice']for r in lots if r['status']=='registered'}),'holding_gap':gap,'conflicts':{**c,'printed_delta':printed_delta,'bid_total':bid_total,'unexplained_difference':bid_total-printed_delta},'observations':observations,'excerpts':p['excerpts'],'source_replay':p['sources'],'boundary':p['boundary'],'prior_snapshot_digest':p['prior_snapshot_digest'],'new_downloads':0,'method_promotions':0}
