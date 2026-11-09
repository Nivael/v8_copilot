"""Merge explicitly reviewed supplements for reading; keep historical inputs intact."""
from hashlib import sha256
from collections import Counter
from canonical_json import digest

IDS={'1225586236','1225610808','1225612083','1225626235','1225649857','1225660311','1225660310','1225568734','1225577951','1225649856'}

def announcement_reading(inputs,ann,context):
 p=inputs.get('announcement_reading')
 if p is None:return None
 if p['version']!=1 or p['through']!=inputs['through']or p['prior_announcement_digest']!=digest(ann)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('reading supplement scope changed')
 if p['method_promotions']!=0 or {s['announcement_id']for s in p['sources']}!=IDS:raise ValueError('reading supplement source scope changed')
 sources={s['announcement_id']:s for s in p['sources']};pages={}
 for q in p['evidence_pages']:
  if not sources[q['announcement_id']]['protected_gate_passed']or q['digest']!=sha256(q['text'].encode()).hexdigest():raise ValueError('reading evidence changed')
  pages[q['announcement_id'],q['page']]=q['text']
 added=[]
 for e in p['events']:
  s=sources[e['announcement_id']];text=''.join(pages[e['announcement_id'],n]for n in e['pages'])
  if e['symbol']!='002514'or e['published_on']!=s['announcement_date']or any(t not in text for t in e['tokens']):raise ValueError('event/source identity absent')
  added.append({**{k:v for k,v in e.items()if k not in ('announcement_id','pages','tokens')},'name':'*ST宝馨','source':{**s,'page':e['pages'][0]},'supporting_sources':[{**s,'page':n}for n in e['pages'][1:]],'observation':context(e),'event_key':'supplement:'+e['id'],'source_record_count':1})
 if len(added)!=9 or len({e['id']for e in added})!=9 or any(e['id']in {r['id']for r in ann['verified_events']}for e in added):raise ValueError('duplicate or missing reading fact')
 # Match original auction identities to later receipts; do not infer by totals.
 for aid,receipt,tokens in [('1225568734','1225660311',['万苏苏','T9582','450万']),('1225568734','1225626235',['曹沈阳','200万']),('1225577951','1225626235',['高远','200万'])]:
  a=''.join(t for (k,_),t in pages.items()if k==aid);b=''.join(t for (k,_),t in pages.items()if k==receipt)
  if not all(t in a and t in b for t in tokens):raise ValueError('auction/registration identity missing')
 # Future 10万 row has no proof tying it to the defaulted bid; never certify it.
 if p['schedule_identity_confirmed']is not False:raise ValueError('future scheduled lot cannot be claimed as identified reauction')
 docs={(e['symbol'],s['sha256'])for e in ann['verified_events']for s in [e['source'],*e.get('supporting_sources',[])]}
 old_docs=len(docs);docs.update(('002514',s['sha256'])for s in sources.values())
 events=sorted([*ann['verified_events'],*added],key=lambda e:(e['published_on'],e['symbol'],e['id']))
 days=Counter((e['symbol'],e['published_on'])for e in events)
 events=[{**e,'observation_key':e['symbol']+':'+e['published_on'],'same_company_day_facts':days[e['symbol'],e['published_on']]}for e in events]
 return {**ann,'verified_events':events,'raw_fact_records':ann['raw_fact_records']+len(added),'deduplicated_event_count':len(events),'verified_documents':len(docs),'body_reads_this_refresh':0,'coverage_note':f'含此前单列补证7份及本轮竞拍原件3份；10份补充来源按SHA去重，其中简式报告只作支持来源、不新增事件。不是本轮重读全部文件。','supplement':{'files':len(docs)-old_docs,'facts':len(added),'source_pages':sum(s['pages']for s in sources.values()),'new_files_this_round':3,'new_pages_this_round':10,'all_source_files':len(sources),'old_fact_records':ann['raw_fact_records'],'old_reading_items':len(ann['verified_events']),'old_documents':ann['verified_documents'],'unique_company_days':len(days),'schedule_identity_confirmed':False,'sources':list(sources.values())},'boundary':ann['boundary']+' 本轮统一阅读包含后续登记、部分悔拍及抵债补证；同公司同日多项事实共享一个日期行情观察，不按文件或买受人数累计独立验证。'}
