"""Separate prior arrangement, first-day notice and transport path dates."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from collections import Counter
from hashlib import sha256
from canonical_json import digest

IDS={'1225340351':'2026-05-30','1225340352':'2026-05-30','1225356346':'2026-06-08'}

def apply_huke_date_proof(inputs,reading,context):
 p=inputs.get('huke_date_proof')
 if p is None:return None,reading
 if p['version']!=1 or p['through']!=inputs['through']or p['reading_digest']!=digest(reading)or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('Huke date proof binding changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if set(sources)!=set(IDS)or p['method_promotions']!=0 or p['earliest_publication_certified']is not False:raise ValueError('Huke source or time scope changed')
 for aid,s in sources.items():
  meta=s['metadata'];day=datetime.fromtimestamp(meta['announcementTime']/1000,timezone.utc).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
  if s['published_on']!=IDS[aid]or day!=s['published_on']or meta['secCode']!='600608'or meta['announcementId']!=aid or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or not s['protected_gate_passed']:raise ValueError('official calendar/issuer identity changed')
  for page,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(page)-1]:raise ValueError('Huke evidence page changed')
  text=''.join(s['selected_pages'].values())
  if '600608'not in text or '2026年6月8日'not in text:raise ValueError('Huke effective date absent')
  tokens={'1225340351':['2026-044','2026年5月29日','股票终止上市的决定'],'1225340352':['2026-045','退市整理期交易起始日','2026年5月30日'],'1225356346':['2026-046','交易首日','2026年6月8日']}[aid]
  if any(t not in text for t in tokens):raise ValueError('distinct announcement stages were conflated')
 public_sources={aid:{k:v for k,v in src.items()if k not in ('selected_pages','page_hashes')}for aid,src in sources.items()}
 old=next(e for e in reading['verified_events']if e['id']=='pre_rule_boundary_600608')
 if old['published_on']!='2026-06-07'or old['source']['sha256']!=sources['1225356346']['sha256']or old['source']['catalog_url']!=p['legacy_catalog_url']:raise ValueError('old carrier/first-day identity differs')
 if p['legacy_catalog_title']!=sources['1225340352']['title'] or p['legacy_catalog_id']!=old['source']['catalog_announcement_id']:raise ValueError('legacy directory title does not name the prior arrangement')
 if '2026-05-30'not in p['legacy_catalog_url']or p['legacy_catalog_role']!='earlier_arrangement_notice':raise ValueError('old directory cannot identify a later first-day notice')
 new={**old,'published_on':'2026-06-08','source':{**public_sources['1225356346'],'page':1},'supporting_sources':[{**public_sources['1225356346'],'page':3}],'title':'退市整理首日：正式目录日与实施日均为6月8日','change':'首日风险提示正式目录列6月8日，文件也落款6月8日；该日进入退市整理，不是已摘牌。','interpretation':'5月30日是不同的前置安排公告。旧路径6月7日不认证最早公开日，行情按正式目录日另算，旧情景保留追溯。','evidence_detail':'044/045/046号分开，正式目录时间戳按北京时间日期；元数据0点不认证实际发布分钟。','watch':'最早公开时点、正式更正与实际摘牌另需证据；当前全名单独立性未完成。'}
 for k in ('alternate_published_on','alternate_observation','date_uncertainty'):new.pop(k,None)
 new['observation']=context(new)
 if new['observation']!=old['alternate_observation']:raise ValueError('same corrected window must retain prior computed alternative')
 prior_record={k:v for k,v in old.items()}
 events=[]
 for e in p['events']:
  s=public_sources[e['source_id']]
  if e['published_on']!=s['published_on']or e['symbol']!='600608':raise ValueError('new prior fact date differs')
  events.append({**{k:v for k,v in e.items()if k!='source_id'},'name':'*ST沪科','source':{**s,'page':1},'supporting_sources':[{**s,'page':2},{**s,'page':3}],'observation':context(e),'event_key':'huke:'+e['id'],'source_record_count':1})
 if len(events)!=2 or {e['id']for e in events}!={'huke_termination_decision','huke_terminal_arrangement'}:raise ValueError('missing or duplicate prior stage')
 merged=sorted([*(new if e['id']==old['id']else e for e in reading['verified_events']),*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));counts=Counter((e['symbol'],e['published_on'])for e in merged);merged=[{**e,'observation_key':e['symbol']+':'+e['published_on'],'same_company_day_facts':counts[e['symbol'],e['published_on']]}for e in merged]
 docs={(e['symbol'],s['sha256'])for e in reading['verified_events']for s in [e['source'],*e.get('supporting_sources',[])]};docs.update(('002514',s['sha256'])for s in reading['supplement']['sources']);docs.update(('600608',s['sha256'])for s in sources.values())
 current={**reading,'supplement':{**reading['supplement'],'unique_company_days':len(counts)},'huke_source_update_digest':p['content_digest'],'verified_events':merged,'verified_documents':len(docs),'raw_fact_records':reading['raw_fact_records']+2,'deduplicated_event_count':len(merged),'coverage_note':reading['coverage_note']+' 本轮另补沪科5月30日两份前置公告；6月8日首日提示仅纠正来源日期、不生新事项；原目录数字不扩充。'}
 view={'through':inputs['through'],'sources':[{k:v for k,v in s.items()if k not in ('selected_pages','page_hashes')}for s in sources.values()],'effective_on':'2026-06-08','formal_published_on':'2026-06-08','legacy_path_date':'2026-06-07','legacy_catalog_url':p['legacy_catalog_url'],'legacy_catalog_role':p['legacy_catalog_role'],'historical_record':prior_record,'current_record':next(e for e in merged if e['id']==old['id']),'prior_events':events,'earliest_publication_certified':False,'same_firstday_bytes':True,'new_unique_documents':2,'new_facts':2,'method_promotions':0}
 return view,current
