"""Pre-July warning grounds, distinct from July notice coverage and later removal."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
import re
from canonical_json import digest
EXPECTED={
 '1225231978':('000016','2026-04-29',('持续经营重大不确定性','2026年4月30日','-6,083,071,689.95')),
 '1224696715':('000698','2025-10-01',('行政处罚事先告知书','2025年10月10日')),
 '1225074277':('000698','2026-04-03',('2025年11月28日','行政处罚决定书','作出行政处罚决定书之日起已满十二个月')),
 '1225251583':('002102','2026-04-29',('否定意见内部控制审计报告','2026年4月30日')),
 '1225394062':('002102','2026-06-30',('连续两个会计年度','内控整改工作组')),
 '1225227092':('002175','2026-04-29',('299,472,346.17','2026年4月30日')),
 '1224888881':('002586','2025-12-20',('2025年12月23日','继续被实施其他风险警示','2025年4月29日')),
 '1223155412':('002586','2025-04-19',('2025年4月21日','叠加实施其他风险警示')),
 '1225241865':('002691','2026-04-29',('扣除后的营业收入低于3亿元','2026年4月30日')),
 '1225156047':('002977','2026-04-23',('2026年4月24日','*ST天箭','-171,421,984.20')),
}
CASE_SCOPE={
 '000016':('2026-04-30',{'1225231978'}),
 '000698':('2025-10-10',{'1224696715','1225074277'}),
 '002102':('2026-04-30',{'1225251583','1225394062'}),
 '002175':('2026-04-30',{'1225227092'}),
 '002586':('2025-12-23',{'1223155412','1224888881'}),
 '002691':('2026-04-30',{'1225241865'}),
 '002977':('2026-04-24',{'1225156047'}),
}
def origin_document_date(source):
 text=source['selected_pages'][str(source['pages'])];tail=text[text.rfind('董事会'):]if'董事会'in text else text[-250:]
 digits={c:str(n)for n,c in enumerate('〇一二三四五六七八九')};digits.update({'零':'0','○':'0','O':'0','Ｏ':'0'})
 matches=re.findall(r'([0-9二〇○零OＯ一三四五六七八九]{4})年([一二三四五六七八九十〇零0-9]{1,3})月([一二三四五六七八九十〇零0-9]{1,3})日',tail)
 if not matches:raise ValueError('warning-origin printed date missing')
 y,m,d=matches[-1]
 def num(x):
  if x.isdigit():return int(x)
  if '十'in x:
   a,b=x.split('十');return int(digits.get(a,'1'))*10+int(digits.get(b,'0'))
  return int(''.join(digits[c]for c in x))
 year=int(y)if y.isdigit()else int(''.join(digits[c]for c in y));return datetime(year,num(m),num(d)).date().isoformat()

def initial_warning_origin(inputs,reading,day,context):
 p=inputs.get('initial_warning_origin')
 if p is None:return None,reading
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('warning-origin packet changed')
 if p['prior_reading_digest']!=digest(reading)or p['prior_day_digest']!=digest(day)or p['anchor']!='2026-07-03'or p['through']!=inputs['through']:raise ValueError('warning-origin prior/cutoff changed')
 if p['scope_digest']!=digest({k:inputs[k]for k in ('calendar','members','fixed_prices','benchmarks','through')}):raise ValueError('warning-origin market scope changed')
 if p['method_promotions']!=0 or p['full_membership_certification_added']is not False:raise ValueError('warning grounds cannot promote methods or certify full roster')
 sources={s['announcement_id']:s for s in p['sources']}
 if set(sources)!=set(EXPECTED)or len(p['sources'])!=10 or len(p['rows'])!=10 or {r['source_id']for r in p['rows']}!=set(EXPECTED):raise ValueError('warning-origin source set changed')
 for aid,s in sources.items():
  c,d,tokens=EXPECTED[aid];m=s['raw_item'];date=datetime.fromtimestamp(m['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if (s['symbol'],s['announcement_date'])!=(c,d)or m['secCode']!=c or str(m['announcementId'])!=aid or date!=d or s['url']!='https://static.cninfo.com.cn/'+m['adjunctUrl']or s['title']!=re.sub('<[^>]+>','',m['announcementTitle'])or s['protected_gate_passed']is not True:raise ValueError('warning-origin official metadata conflict')
  if s['pages']!=len(s['page_hashes'])or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('warning-origin pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('warning-origin page changed')
  text=''.join(s['selected_pages'].values())
  if c not in s['selected_pages']['1']or any(t not in text for t in tokens):raise ValueError('warning-origin required clause absent')
 events=[]
 for r in p['rows']:
  s=sources[r['source_id']];c,d,_=EXPECTED[r['source_id']]
  if r['symbol']!=c or r['published_on']!=d or r['id']!='warning_origin_'+r['source_id']or r['entity_scope']!='issuer'or r['document_dated_on']!=origin_document_date(s)or not r['evidence_pages']or any(str(n)not in s['selected_pages']for n in r['evidence_pages']):raise ValueError('warning-origin event/date/page conflict')
  public={k:v for k,v in s.items()if k not in ('selected_pages','page_hashes','raw_item')};e={**{k:v for k,v in r.items()if k!='source_id'},'source':{**public,'page':r['evidence_pages'][0]},'source_record_count':1,'observation_key':c+':'+d,'same_company_day_facts':1,'background_only':d<inputs['calendar'][0]};e['observation']=context(e);events.append(e)
 if {s['sha256']for s in sources.values()}&{e['source']['sha256']for e in reading['verified_events']}or {e['id']for e in events}&{e['id']for e in reading['verified_events']}:raise ValueError('warning-origin documents already counted')
 cases=[]
 if len(p['cases'])!=7 or {c['symbol']for c in p['cases']}!=set(CASE_SCOPE):raise ValueError('warning-origin case set changed')
 for c in p['cases']:
  date,ids=CASE_SCOPE[c['symbol']];base=next(r for r in day['rows']if r['symbol']==c['symbol'])
  if c['effective_on']!=date or set(c['source_ids'])!=ids or len(c['source_ids'])!=len(ids)or c['name']!=base['name']:raise ValueError('warning-origin case/effective-source binding changed')
  if c['symbol']=='002977'and c['internal_conflict_unresolved']is not True:raise ValueError('July internal name conflict must remain')
  cases.append({**c,'sources':[next(e for e in events if e['source']['announcement_id']==aid)for aid in c['source_ids']],'july_source':base['source'],'observation':base['observation'],'full_period':base['full_period']})
 merged=sorted([*reading['verified_events'],*events],key=lambda e:(e['published_on'],e['symbol'],e['id']));days=Counter((e['symbol'],e['published_on'])for e in merged);current={**reading,'verified_events':merged,'verified_documents':reading['verified_documents']+10,'raw_fact_records':reading['raw_fact_records']+10,'deduplicated_event_count':len(merged),'verified_companies':len({e['symbol']for e in merged}),'supplement':{**reading['supplement'],'unique_company_days':len(days)},'initial_warning_origin_digest':p['content_digest'],'coverage_note':reading['coverage_note']+' 六家警示依据及天箭实施原件另补10份35页；期初42/150阅读覆盖不虚增，原异动文件缺原因与内部简称冲突历史保留。'}
 return {'anchor':p['anchor'],'through':p['through'],'cases':cases,'rows':events,'counts':{'new_files':10,'new_pages':sum(s['pages']for s in sources.values()),'resolved_general_notice_basis':6,'cases':7,'timely_reading':42,'remaining_timely':108,'pre_calendar_documents':sum(e['background_only']for e in events),'full_membership_certification_added':0},'method_promotions':0,'boundary':'补齐本批六家公司警示触发依据，不认证全部风险、连续状态或历史全表。天箭4月实施更名有原件，7月正文内部差异仍未获更正解释；旧5%条款只属当年当日，不替代7月6日以后制度口径。'},current
