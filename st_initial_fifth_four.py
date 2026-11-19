"""Fifth code-ordered coverage batch; initial facts and later returns stay separate."""
from collections import Counter
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest
from st_initial_four import quote_audit
CODES=['002199', '002207', '002211', '002214']
IDS={'1225322166': '002199', '1225219075': '002199', '1225213294': '002207', '1225165170': '002211', '1225403248': '002214', '1225037593': '002214'}
CLAUSES={('1225219075', 2): ['34,304.34', '18,221.14'], ('1225322166', 1): ['补充材料'], ('1225213294', 1): ['295,103,227.16', '2026年4月29日'], ('1225165170', 1): ['持续经营重大不确定性', '2026年4月24日'], ('1225037593', 2): ['330,763,727.44', '230,762,658.56'], ('1225403248', 1): ['补充材料', '2026年3月26日']}
VISUAL=[]
DEFINITIONS=[{'symbol': '002199', 'primary': '1225219075', 'pages': [1, 2, 3], 'risk_group': '营收过线，申请仍待审核', 'known_at_anchor': '2025年扣除后营收34304.34万元、归母净资产18221.14万元，标准无保留审计，但归母仍亏损5002.11万元。4月27日提交申请；5月22日仍在补材料，不能视为正式摘帽。', 'watch': '分别核正式核准、生效日与后续经营数据；程序进展、盈利恢复和价格结果分别判断。', 'supporting': [{'id': '1225322166', 'pages': [1, 2], 'note': '进展公告仍为补充材料、是否获批不确定；补材料时间不计入审核期限。'}]}, {'symbol': '002207', 'primary': '1225213294', 'pages': [1, 2, 3], 'risk_group': '亏损与营收不足3亿元共同触发', 'known_at_anchor': '2025年利润总额、归母及扣非净利润均负，扣除后营收295103227.16元；4月29日起实施退市风险警示。整改计划不是已经兑现的经营修复。', 'watch': '分别核正式核准、生效日与后续经营数据；程序进展、盈利恢复和价格结果分别判断。', 'supporting': []}, {'symbol': '002211', 'primary': '1225165170', 'pages': [1, 2], 'risk_group': '连续亏损与持续经营疑虑', 'known_at_anchor': '2023至2025年扣非前后净利润孰低均负，2025年审计为带持续经营重大不确定性段落的无保留意见，4月24日起继续ST。不能误写为保留意见，也不能认为疑虑已消除。', 'watch': '分别核正式核准、生效日与后续经营数据；程序进展、盈利恢复和价格结果分别判断。', 'supporting': []}, {'symbol': '002214', 'primary': '1225037593', 'pages': [1, 2], 'risk_group': '营收过线，7月初仍在补材料', 'known_at_anchor': '2025年扣除后营收330763727.44元、归母净资产1313851692.13元，标准无保留审计，但净利润仍为-230762658.56元。3月26日提交申请，7月2日仍在补材料，不能倒填后来8月摘帽为期初已完成。', 'watch': '分别核正式核准、生效日与后续经营数据；程序进展、盈利恢复和价格结果分别判断。', 'supporting': [{'id': '1225403248', 'pages': [1], 'note': '进展公告仍为补充材料、是否获批不确定；补材料时间不计入审核期限。'}]}]
SOURCE_SHA={'1225322166': '8a1a7bd5bc2c7e25c35dd6bc8212cc02015289ea209f30b296218d34caa482c5', '1225219075': 'caab18f9bbc684e2680ed892b543cbe6ab6d03a945113cdec377b8a14dfb9336', '1225213294': '09d2c906df96356483c945943fa872a8c1c6af25fe5984480d5c9b6669df7006', '1225165170': '29bb53e45c9fabef671934ef4036a4c860c291c24749d416259a154322dea85e', '1225403248': 'd4461c2dd2cfd0d293067b1662707ce01a92871da0324ea0652f632c4e8b8dc6', '1225037593': '928865af1202ad0c5bfad3f9843f6584c2d583f1a75fb70d796c001324259521'}
def initial_fifth_four(inputs,prior,current):
 p=inputs.get('initial_fifth_four')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('fifth four packet changed')
 if not prior or not current or p['prior_inventory_digest']!=digest(prior['inventory'])or p['current_extension_digest']!=digest(current):raise ValueError('fifth four prior changed')
 missing=sorted(r['symbol']for r in prior['inventory']if not r['has_timely_reading_facts'])
 if len(prior['inventory'])!=150 or missing[:4]!=CODES or p['selection']!=CODES or sum(r['has_timely_reading_facts']for r in prior['inventory'])!=58:raise ValueError('fifth four selection changed')
 fresh=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(fresh)or current['through']!='2026-11-19':raise ValueError('fifth four market changed')
 visual=p['visual_read']
 if visual!=VISUAL:raise ValueError('fifth four visual reading changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(p['sources'])!=6 or set(sources)!=set(IDS):raise ValueError('fifth four sources changed')
 for aid,s in sources.items():
  meta=s['raw_item']
  if s['sha256']!=SOURCE_SHA[aid]:raise ValueError('fifth four source SHA changed')
  pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!=IDS[aid]or s['symbol']!=IDS[aid]or re.sub('<[^>]+>','',meta['announcementTitle'])!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub>'2026-07-03'or not s['protected_gate_passed']:raise ValueError('fifth four identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('fifth four pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('fifth four page changed')
  from st_initial_warning_origin import origin_document_date
  if origin_document_date(s)!=s['document_dated_on']:raise ValueError('fifth four printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(t not in sources[aid]['selected_pages'][str(n)]for t in tokens):raise ValueError('fifth four risk/remediation clause changed')
 audit=quote_audit(p['cross_sources'],fresh,codes=CODES)
 from st_regime_comparison import build
 early=next(c for c in build(fresh)['comparisons']if c['key']=='20');full=current['full_comparison'];rows=[]
 public=lambda s:{k:v for k,v in s.items()if k not in ['raw_item','selected_pages','page_hashes']}
 for definition in DEFINITIONS:
  code=definition['symbol'];aid=definition['primary'];risk=definition['risk_group'];known=definition['known_at_anchor'];watch=definition['watch'];pages=definition['pages'];supports=[(r['id'],r['pages'],r['note'])for r in definition['supporting']]
  comps={}
  for key,c in [('early20',early),('full',full)]:
   r=next(r for r in c['fixed_after']['rows']if r['symbol']==code);comps[key]={'anchor':c['fixed_after']['anchor'],'through':c['fixed_after']['through'],'days':c['after']['days'],'stock_pct':r['return_pct'],'market_pct':c['after']['market_change_pct'],'st_pct':c['after']['reference_change_pct'],'gap':r['gap']}
  rows.append({'symbol':code,'name':next(r['name']for r in prior['inventory']if r['symbol']==code),'risk_group':risk,'known_at_anchor':known,'watch':watch,'source':public(sources[aid]),'pages':pages,'supporting':[{'source':public(sources[x]),'pages':ns,'note':note}for x,ns,note in supports],'comparisons':comps})
 inventory=[]
 for r in prior['inventory']:
  if r['symbol']in CODES:
   ss=[s for s in sources.values()if s['symbol']==r['symbol']];inventory.append({**r,'has_timely_reading_facts':True,'new_this_round':True,'latest_fact_on':max(s['published_on']for s in ss),'fact_ids':r['fact_ids']+['initial_fifth_four:'+s['announcement_id']for s in ss]})
  else:inventory.append({**r,'new_this_round':False})
 return {'anchor':'2026-07-03','through':'2026-11-19','title':'营收过了门槛，为什么还没摘帽？','intro':'东晶与大立的营收已越过3亿元，但期初摘帽申请仍在审核、经营仍亏损；准油触发亏损与营收门槛的共同条件，宏达因连续亏损及持续经营疑虑继续ST。','window_note':'东晶与大立期初同在申请审核中，7月3日至11月19日前复权收益却分别为-33.36%和+6.88%。相似程序状态不能直接推出相似价格表现；后续公告与市场环境仍需逐段研究，这两例不构成普遍胜率。','rows':rows,'inventory':inventory,'quote_audit':audit,'visual_read':visual,'counts':{'before':58,'after':62,'remaining':88,'members':150,'new_companies':4,'new_files':6,'new_pages':13},'selection_note':'从92家期初事实缺口按代码顺序取前四，不按事后收益筛选；非随机，也不声称前瞻盲选。','boundary':'只确认所选公告当时披露状态，不认证完整官方历史名录或所有警示条件。后来摘帽不倒填期初；盈利、营收、申请与正式核准分别读。前复权同窗收益描述结果，不识别公告及制度净因果。','method_promotions':0,'full_membership_certification_added':False}
