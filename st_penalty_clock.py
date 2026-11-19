"""Decision dates are not automatic removal dates; preserve the old evidence chain."""
from datetime import date,datetime
from zoneinfo import ZoneInfo
from collections import Counter
from hashlib import sha256
import re
from canonical_json import digest
from st_initial_warning_origin import origin_document_date
EXPECTED={'1224833816':('000698','2025-11-29',('2025年11月28日','700万元')),'1223411160':('002586','2025-04-30',('2025年4月29日','700万元')),'1225470994':('002586','2026-08-13',('2026年8月12日','尚需深圳证券交易所核准','已满十二个月','2025年11月28日'))}
REG={'000698':('https://www.csrc.gov.cn/liaoning/c103750/c7598233/content.shtml','2025-11-25','2025-11-28'),'002586':('https://www.csrc.gov.cn/ningbo/c104130/c7554933/content.shtml','2025-04-29','2025-04-29')}
def penalty_clock(inputs,reading,origin,day,context):
 p=inputs.get('penalty_clock')
 if p is None:return None,reading
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('penalty-clock packet changed')
 if p['prior_reading_digest']!=digest(reading)or p['prior_origin_digest']!=digest(origin)or p['prior_day_digest']!=digest(day)or p['through']!=inputs['through']:raise ValueError('penalty-clock prior/cutoff changed')
 if p['scope_digest']!=digest({k:inputs[k]for k in ('calendar','through','members','fixed_prices','benchmarks')}):raise ValueError('penalty-clock market scope changed')
 if p['method_promotions']!=0 or p['full_membership_certification_added']is not False:raise ValueError('penalty-clock cannot promote methods or certify full roster')
 sources={s['announcement_id']:s for s in p['sources']};regs={r['symbol']:r for r in p['regulators']}
 if len(p['sources'])!=3 or set(sources)!=set(EXPECTED)or len(p['rows'])!=3 or {r['source_id']for r in p['rows']}!=set(EXPECTED)or len(p['regulators'])!=2 or set(regs)!=set(REG):raise ValueError('penalty-clock source set changed')
 for aid,s in sources.items():
  c,d,tokens=EXPECTED[aid]
  if (s['symbol'],s['announcement_date'])!=(c,d)or s['protected_gate_passed']is not True or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}or len(s['page_hashes'])!=s['pages']:raise ValueError('penalty-clock source identity/pages changed')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('penalty-clock source page changed')
  text=''.join(s['selected_pages'].values())
  if c not in s['selected_pages']['1']or any(t not in text for t in tokens):raise ValueError('penalty-clock source clause missing')
  meta=s.get('metadata')
  if meta:
   if str(meta['announcementId'])!=aid or meta['secCode']!=c or datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()!=d or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']:raise ValueError('penalty-clock official metadata changed')
  elif not any(x['announcement_id']==aid and all(s[k]==x[k]for k in ('symbol','announcement_date','title','url'))for x in inputs['announcement_study']['catalogs'][c]['rows']):raise ValueError('penalty-clock frozen directory changed')
 for c,r in regs.items():
  url,made,received=REG[c];dt=date.fromisoformat(made);token=f'{dt.year}年{dt.month}月{dt.day}日'
  if r['url']!=url or r['decision_made_on']!=made or r['issuer_received_on']!=received or token not in r['normalized_text']or '700万元'not in r['normalized_text']or sha256(r['normalized_text'].encode()).hexdigest()!=r['text_sha256']or r['protected_gate_passed']is not True or not r['page_metadata_pubdate']or not r['historical_availability_basis']:raise ValueError('penalty-clock regulator date/body binding changed')
 replay=p['removal_replay'];old=next(e for e in reading['verified_events']if e['id']=='warning_removed_002586')
 if replay['sha256']!=old['source']['sha256']or replay['url']!=old['source']['url']or len(replay['page_hashes'])!=3 or set(replay['selected_pages'])!={'1','2','3'}:raise ValueError('penalty-clock old removal source changed')
 for n,t in replay['selected_pages'].items():
  if sha256(t.encode()).hexdigest()!=replay['page_hashes'][int(n)-1]:raise ValueError('penalty-clock old removal page changed')
 text=''.join(replay['selected_pages'].values())
 if any(t not in text for t in ('2026年8月31日','2026年8月28日','已满十二个月')):raise ValueError('penalty-clock removal stages missing')
 events=[]
 for r in p['rows']:
  s=sources[r['source_id']];c,d,_=EXPECTED[r['source_id']]
  if r['symbol']!=c or r['published_on']!=d or r['id']!='penalty_clock_'+r['source_id']or r['document_dated_on']!=origin_document_date(s)or r['entity_scope']!='issuer'or not r['evidence_pages']or any(str(n)not in s['selected_pages']for n in r['evidence_pages']):raise ValueError('penalty-clock event/date changed')
  public={k:v for k,v in s.items()if k not in ('selected_pages','page_hashes','metadata')};e={**{k:v for k,v in r.items()if k!='source_id'},'source':{**public,'page':r['evidence_pages'][0]},'supporting_sources':[],'source_record_count':1,'observation_key':c+':'+d,'background_only':d<inputs['calendar'][0]};e['observation']=context(e)
  if r['source_id']!='1225470994':e['supporting_sources']=[{k:regs[c][k]for k in ('title','url','sha256')}|{'page':1,'source_format':'regulator_html','decision_made_on':regs[c]['decision_made_on']}]
  events.append(e)
 if {e['id']for e in events}&{e['id']for e in reading['verified_events']}or {s['sha256']for s in sources.values()}&{e['source']['sha256']for e in reading['verified_events']}:raise ValueError('penalty-clock sources already counted')
 companies=[]
 for c,r in regs.items():
  made=date.fromisoformat(r['decision_made_on']);anniversary=made.replace(year=made.year+1);base=next(x for x in day['rows']if x['symbol']==c);companies.append({'symbol':c,'name':base['name'],'decision_made_on':made.isoformat(),'received_on':r['issuer_received_on'],'anniversary_reference':anniversary.isoformat(),'days_to_reference_at_cutoff':(anniversary-date.fromisoformat(p['through'])).days,'at_july': '十二个月参照日尚未到'if anniversary>date(2026,7,3)else'参照日已过，但当时仍是ST','full_period':base['full_period'],'regulator':{k:v for k,v in r.items()if k not in ('text','normalized_text')}})
 if not any(r['symbol']=='000698' and r['trade_date']==p['through'] and r['name']=='ST沈化' for r in inputs['members']):raise ValueError('Shenhua endpoint membership changed')
 if any(r['symbol']=='002586'and r['trade_date']>='2026-08-31'for r in inputs['members']):raise ValueError('Weihai remains in ST after effective exit')
 application=next(e for e in events if e['source']['announcement_id']=='1225470994');effective=context({'published_on':'2026-08-31','symbol':'002586'});merged=sorted([*reading['verified_events'],*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));days=Counter((e['symbol'],e['published_on'])for e in merged);current={**reading,'verified_events':merged,'verified_documents':reading['verified_documents']+5,'raw_fact_records':reading['raw_fact_records']+3,'deduplicated_event_count':len(merged),'supplement':{**reading['supplement'],'unique_company_days':len(days)},'penalty_clock_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 沈化/围海另补3份15页PDF及2监管HTML，两个监管正文仅佐证同一决定，不另加事件；旧撤销件重放不重计。'}
 view={'through':p['through'],'companies':companies,'rows':events,'application':application,'removal_event':old,'removal_replay_source':{k:v for k,v in replay.items()if k not in ('selected_pages','page_hashes')},'effective_observation':effective,'stages':{'board_on':'2026-08-12','application_disclosed_on':'2026-08-13','removal_disclosed_on':'2026-08-28','effective_on':'2026-08-31','independent_approval_letter_obtained':False,'days_reference_to_board':(date(2026,8,12)-date(2026,4,29)).days,'days_reference_to_effective':(date(2026,8,31)-date(2026,4,29)).days},'counts':{'new_pdf_files':3,'new_pdf_pages':15,'new_regulator_html':2,'new_events':3,'replayed_old_pdf_files':1,'replayed_old_pdf_pages':3,'timely_reading':42,'remaining_timely':108},'method_promotions':0,'boundary':'一周年仅按决定落款推得日历参照，不是自动摘帽日；申请、撤销安排公告、核准函和实际生效分别看。本轮不取得独立核准函或解释公司选择申请日期的具体原因，不把后续股价差异归因为处罚时钟。'}
 return view,current
