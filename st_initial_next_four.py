"""Second code-ordered coverage batch; initial facts and later returns stay separate."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest
from st_initial_four import quote_audit
CODES=['000615','000669','000752','000826']
IDS={'1225326692':'000615','1225197985':'000615','1225197981':'000615','1225251137':'000669','1225251135':'000669','1225251124':'000669','1225347065':'000752','1225197995':'000752','1225196578':'000752','1225384023':'000826','1225242879':'000826'}
VISUAL_SHA='fa33f81863f3f1f85e1ee086ef536df8d6beb934e974cc9d7c69590950ec100d'
CLAUSES={
 ('1225326692',1):['2026年4月24日','补充材料阶段','不确定性'],('1225197981',1):['1,858,541,601.39','标准无保留意见','主要银行账户已解除冻结'],('1225197981',2):['-624,412,913.41','968,367,410.51'],('1225197981',3):['重整计划已经执行完毕','尚存在不确定性'],
 ('1225251124',2):['带强调事项段的无保留意见的内部控制审计报告'],('1225251124',3):['部分其他风险警示','保留意见','持续经营能力存在不确定性'],('1225251135',1):['31,089.28','无法','充分、适当的审计证据'],('1225251135',2):['庭外重组','146,461.78'],('1225251137',1):['丧失对沙河金通的控制权','不影响已对财务报告内部控制发表的审计意见'],
 ('1225347065',1):['审核和补充材料阶段','裁定受理'],('1225197995',1):['2026年4月28日','申请撤销其他风险警示'],('1225197995',2):['331,390,718.71','资金占用问题已整改完毕'],('1225196578',1):['2026年4月24日','裁定受理','2026年4月28日'],
 ('1225384023',2):['2026年6月23日','预重整期间延长三个月','尚未收到法院裁定受理重整申请'],('1225242879',1):['期末归属于母公司净资产为负值','2026年4月30日','叠加实施其他风险警示'],
}
def printed_date(s,visual):
 if s['announcement_id']=='1225197985':return visual['document_dated_on']
 from st_initial_warning_origin import origin_document_date
 return origin_document_date(s)
def initial_next_four(inputs,prior,current):
 p=inputs.get('initial_next_four')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('next four packet changed')
 if not prior or not current or p['prior_inventory_digest']!=digest(prior['inventory'])or p['current_extension_digest']!=digest(current):raise ValueError('next four prior changed')
 missing=sorted(r['symbol']for r in prior['inventory']if not r['has_timely_reading_facts'])
 if len(prior['inventory'])!=150 or missing[:4]!=CODES or p['selection']!=CODES or sum(r['has_timely_reading_facts']for r in prior['inventory'])!=46:raise ValueError('next four selection changed')
 fresh=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(fresh)or current['through']!='2026-11-19':raise ValueError('next four market changed')
 visual=p['visual_read']
 if visual['announcement_id']!='1225197985'or visual['page']!=2 or visual['image_sha256']!=VISUAL_SHA or visual['document_dated_on']!='2026-04-23'or visual['mode']!='manual_rendered_page'or visual['bank_accounts_reported']!={'total':30,'normal':27,'closed':1,'remaining_scope':'部分子公司账户仍涉司法冻结'}:raise ValueError('next four visual reading changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(p['sources'])!=11 or set(sources)!=set(IDS):raise ValueError('next four sources changed')
 for aid,s in sources.items():
  meta=s['raw_item'];pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!=IDS[aid]or s['symbol']!=IDS[aid]or meta['announcementTitle']!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub>'2026-07-03'or not s['protected_gate_passed']:raise ValueError('next four identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('next four pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('next four page changed')
  if printed_date(s,visual)!=s['document_dated_on']:raise ValueError('next four printed date changed')
 if sources['1225197985']['selected_pages']['2']!='2':raise ValueError('next four visual extraction boundary changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(t not in sources[aid]['selected_pages'][str(n)]for t in tokens):raise ValueError('next four risk/remediation clause changed')
 audit=quote_audit(p['cross_sources'],fresh,codes=CODES)
 from st_regime_comparison import build
 early=next(c for c in build(fresh)['comparisons']if c['key']=='20');full=current['full_comparison'];rows=[]
 definitions=[
 ('000615','1225197981','修复披露与撤销申请，仍待审核','原负净资产、持续经营及主要账户冻结警示已有修复披露：2025年末归母净资产为正、标准无保留意见，公司披露重整计划已执行完毕；仍亏损。5月23日原件称撤销申请在补材料，不能写成已经正式摘帽。','核正式审核决定及生效日，分别看主账户与其他子公司账户；修复披露不等于全部风险消失。',[1,2,3,4], [('1225326692',[1],'5月进展仅到补材料，申请不是批准。'),('1225197985',[1,2],'专项第2页无法有效提取正文，已看渲染页：30个存款账户中27个恢复、1个注销，仍列部分子公司账户冻结；与申请中的主要账户解冻范围分开。')]),
 ('000669','1225251124','只申请撤销部分警示，其他仍在','内控旧否定事项有修复，2025内控审计为带强调事项段的无保留意见；财报却仍为保留意见并有持续经营重大不确定性。公司明确即使撤销部分警示，仍继续ST；庭外重组不等于法院正式受理重整。','分别核内控与财报意见、外部担保和持续经营；部分撤销、庭外重组、受理和执行不能互换。',[1,2,3,4],[('1225251135',[1,2,3,4],'财报保留基础涉及担保预计负债证据不足，另有持续经营疑虑，不能用内控意见覆盖。'),('1225251137',[1,2],'内控强调事项涉及子公司失控及工商变更，本段不影响已发表内控意见。')]),
 ('000752','1225197995','旧警示申请撤销，另有正式重整受理','资金占用等旧其他警示有整改和撤销申请，但4月24日已正式受理公司重整，4月28日起因此实施退市风险警示；6月3日旧警示撤销仍在审核补材。不是只有一项正在申请摘帽。','核不同警示分别撤销及重整计划、投资款和执行；受理不是重整成功。',[1,2,3],[('1225196578',[1,3,4,6,7],'正式受理与预重整不同，已有协议仍有履约及重整失败风险。'),('1225347065',[1,2],'6月进展同时保留申请审核补材及法院已受理的状态。')]),
 ('000826','1225242879','负净资产警示，预重整继续延期','2025年末净资产负值，另叠加三年扣非前后孰低亏损及持续经营不确定性警示，4月30日起实施。6月24日披露预重整再延三个月，仍未收到正式受理重整文书；延期不是受理或成功。','核正式受理文件、重整方案与年度财务修复，延期不当新增资金到账或风险解除。',[1,2,3,4],[('1225384023',[1,2,3],'6月23日收到延期决定；未收到受理文书的状态只到本件披露日。')]),
 ]
 public=lambda s:{k:v for k,v in s.items()if k not in ['raw_item','selected_pages','page_hashes']}
 for code,aid,risk,known,watch,pages,supports in definitions:
  comps={}
  for key,c in [('early20',early),('full',full)]:
   r=next(r for r in c['fixed_after']['rows']if r['symbol']==code);comps[key]={'anchor':c['fixed_after']['anchor'],'through':c['fixed_after']['through'],'days':c['after']['days'],'stock_pct':r['return_pct'],'market_pct':c['after']['market_change_pct'],'st_pct':c['after']['reference_change_pct'],'gap':r['gap']}
  rows.append({'symbol':code,'name':next(r['name']for r in prior['inventory']if r['symbol']==code),'risk_group':risk,'known_at_anchor':known,'watch':watch,'source':public(sources[aid]),'pages':pages,'supporting':[{'source':public(sources[x]),'pages':ns,'note':note}for x,ns,note in supports],'comparisons':comps})
 inventory=[]
 for r in prior['inventory']:
  if r['symbol']in CODES:
   ss=[s for s in sources.values()if s['symbol']==r['symbol']];inventory.append({**r,'has_timely_reading_facts':True,'new_this_round':True,'latest_fact_on':max(s['published_on']for s in ss),'fact_ids':r['fact_ids']+['initial_next_four:'+s['announcement_id']for s in ss]})
  else:inventory.append({**r,'new_this_round':False})
 return {'anchor':'2026-07-03','through':'2026-11-19','title':'申请撤销、部分修复、正式受理与预重整延期，要分开看','intro':'这四家在期初已有不同程度的修复或程序进展，但仍受到不同约束。美谷申请待审核、金鸿只撤部分警示、西发已正式受理重整、启环预重整延期；不能都压成一个ST标签或统一摘帽预期。','rows':rows,'inventory':inventory,'quote_audit':audit,'visual_read':visual,'counts':{'before':46,'after':50,'remaining':100,'members':150,'new_companies':4,'new_files':11,'new_pages':36},'selection_note':'按上一轮104家缺口代码顺序取前四，不按事后涨跌排序；不是随机样本，也不声称前瞻盲选。比较路由实际拆成四个单股核对，晚于期初的旧库快照不当当时事实。','boundary':'每个状态只由对应披露日原件支持，不认证此后持续不变或全部风险解除；只比较共同窗口，不分摊公告净因果。新增正文覆盖不是完整官方名录认证，旧批次原样保留。','method_promotions':0,'full_membership_certification_added':False}
