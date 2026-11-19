"""Seventh code-ordered coverage batch; initial facts and later returns stay separate."""
from collections import Counter
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest
from st_initial_four import quote_audit
CODES=['002424', '002431', '002485', '002501']
IDS={'1225220340': '002424', '1225220339': '002424', '1225193616': '002431', '1225250484': '002501', '1225250474': '002501', '1225244457': '002485', '1225043459': '002424', '1224888781': '002424', '1224000135': '002424', '1218685262': '002485'}
CLAUSES={('1224888781', 3): ['作出行政处罚决定书之日起已满十二个月'], ('1224000135', 1): ['2025年6月30日'], ('1225220340', 1): ['21,222.15', '5,856.95', '15,365.20'], ('1225244457', 92): ['1,033,611.18', '12,408,550.00'], ('1218685262', 2): ['1亿元'], ('1225250484', 1): ['4,352.26']}
VISUAL=[{'announcement_id': '1225220340', 'page': 1}, {'announcement_id': '1225220340', 'page': 2}, {'announcement_id': '1225220340', 'page': 3}, {'announcement_id': '1225220339', 'page': 1}, {'announcement_id': '1225220339', 'page': 2}, {'announcement_id': '1225193616', 'page': 1}, {'announcement_id': '1225193616', 'page': 2}, {'announcement_id': '1225193616', 'page': 3}, {'announcement_id': '1225193616', 'page': 4}, {'announcement_id': '1225250484', 'page': 1}, {'announcement_id': '1225250484', 'page': 2}, {'announcement_id': '1225250474', 'page': 1}, {'announcement_id': '1225250474', 'page': 2}, {'announcement_id': '1225250474', 'page': 3}, {'announcement_id': '1225250474', 'page': 4}, {'announcement_id': '1225244457', 'page': 6}, {'announcement_id': '1225244457', 'page': 18}, {'announcement_id': '1225244457', 'page': 92}, {'announcement_id': '1225244457', 'page': 129}, {'announcement_id': '1225244457', 'page': 131}, {'announcement_id': '1225043459', 'page': 1}, {'announcement_id': '1225043459', 'page': 2}, {'announcement_id': '1225043459', 'page': 17}, {'announcement_id': '1225043459', 'page': 18}, {'announcement_id': '1225043459', 'page': 19}, {'announcement_id': '1225043459', 'page': 20}, {'announcement_id': '1224888781', 'page': 1}, {'announcement_id': '1224888781', 'page': 2}, {'announcement_id': '1224888781', 'page': 3}, {'announcement_id': '1224888781', 'page': 4}, {'announcement_id': '1224888781', 'page': 5}, {'announcement_id': '1224000135', 'page': 1}, {'announcement_id': '1224000135', 'page': 2}, {'announcement_id': '1224000135', 'page': 3}, {'announcement_id': '1224000135', 'page': 4}, {'announcement_id': '1224000135', 'page': 5}, {'announcement_id': '1218685262', 'page': 1}, {'announcement_id': '1218685262', 'page': 2}, {'announcement_id': '1218685262', 'page': 3}, {'announcement_id': '1218685262', 'page': 4}]
DEFINITIONS=[{'symbol': '002424', 'primary': '1224888781', 'pages': [1, 2, 3], 'risk_group': '旧内控警示撤销后，财报虚假记载再次触发ST', 'known_at_anchor': '2025年6月30日旧内控警示已撤销；12月23日因年报虚假记载再次ST。2026年3月27日收到最终处罚决定，4月董事会说明旧内控强调事项影响消除，但2025年财报仍有保留意见：原材料及研发项目可收回价值缺乏充分审计证据。', 'watch': '分别跟踪处罚决定作出日、追溯重述、申请及正式撤销；收到日不代替作出日，满十二个月也不等于自动摘帽。核存货与研发项目的新审计证据。', 'supporting': [{'id': '1224000135', 'pages': [1, 2, 3, 4, 5], 'note': '2025年6月旧内控ST已获核准撤销，当时调查仍在进行。'}, {'id': '1225043459', 'pages': [1, 2, 19, 20], 'note': '3月27日收到最终处罚，3月28日披露；本件未确认决定作出日。公告称未触及重大违法强制退市。'}, {'id': '1225220339', 'pages': [1, 2], 'note': '董事会说明旧内控事项影响消除，处罚类ST仍适用；本件不是独立审计报告全文。'}, {'id': '1225220340', 'pages': [1, 2, 3], 'note': '财报保留意见与旧内控问题分开。原材料账面余额21222.15万元、减值5856.95万元、账面价值15365.20万元；账面价值不是已确认损失。'}]}, {'symbol': '002431', 'primary': '1225193616', 'pages': [1, 2, 3, 4], 'risk_group': '连续亏损与持续经营不确定性共同触发', 'known_at_anchor': '2023—2025年扣非前后净利润孰低值连续为负，且最新审计提示持续经营重大不确定性，4月28日起实施其他风险警示。无保留意见附持续经营段不等于经营风险消除。', 'watch': '核资产处置实际到账、应收回款和融资落实；整改计划不作为已完成修复。', 'supporting': []}, {'symbol': '002485', 'primary': '1218685262', 'pages': [1, 2, 3, 4], 'risk_group': '已摘星，主营盈利与账户冻结仍需跟踪', 'known_at_anchor': '2023年12月25日起正式摘星并实施其他ST，原件列主营盈利较弱及部分银行账户冻结。旧退市警示对应2021年亏损且扣除后营收不足1亿元，不能倒套后来3亿元门槛。2025年报披露年末仍有诉讼冻结存款，不能当作7月3日余额。', 'watch': '核剩余冻结账户与案件、主营盈利和正式撤销文件；股东股份冻结与上市公司存款分开。尚不认证2023年至期初所有状态变化无遗漏。', 'supporting': [{'id': '1225244457', 'pages': [6, 18, 92, 129, 131], 'note': '2025年末冻结存款1033611.18元，ETC保证金2000元、平台保证金12408550元，合计受限资金13444161.18元。股东股份冻结另列；年报4月29日披露，仅核上述关键页。'}]}, {'symbol': '002501', 'primary': '1225250474', 'pages': [1, 2, 3, 4], 'risk_group': '亏损与营收不足3亿元共同触发', 'known_at_anchor': '2025年利润条件为负且扣除后营收不足3亿元，4月30日起实施退市风险警示。另有投资者诉讼：诉请金额、有效判决赔偿、预计赔偿和仍难估计案件应分开。', 'watch': '核新年度财务共同条件与实际经营改善；按诉讼阶段跟踪赔偿。未计提不等于没有风险，诉请不直接当损失。', 'supporting': [{'id': '1225250484', 'pages': [1, 2], 'note': '无保留意见附强调事项。诉请合计57200.04万元；有效判决赔偿4352.26万元，未决普通案件预计赔偿561.49万元，另有基金重审案赔偿难估计。分项诉请相加与披露合计差0.01万元，保留原值，不擅改总额。'}]}]
SOURCE_SHA={'1225220340': 'ae3918f8e8f885218aba82f33caad286b20a4ac456b19fef4ab02012ee547a9c', '1225220339': 'ebbd9856c54da506ed8ada546abc98aad94c27fcfb10ad76f0b9439831101325', '1225193616': 'd231fd80777fb06b252f4ae943948b785b257fee6b95700b749383fb9f120d4b', '1225250484': '15b11bf035d2ace49dafa6576bd949d3bfa4ffc9ad4adea2e3c45546cc3911a3', '1225250474': 'd955d2508dc425ca9d55deba5ae40454c8345c77da581e1f3b88b8eec955b504', '1225244457': '7de4662f1cd74eb2bd5601980e0370f71fc412846d7b6b5a1c3cb1c479a92585', '1225043459': '369a04e7d87237800f5c92fa0f5bbaa8542da880418e7ce5f994ac955c657b06', '1224888781': 'dc5a8c0145081ccabb48a3239a38724ceb2567bacdac97484ae69af20bf11fa2', '1224000135': 'b75efa9cc528f813e330aa6cc92cb77f42d26396210aa83d4a5b645e17d20544', '1218685262': '00cb1ba476333ff464ca543a02ebff43704d33964cf2f8894292009e830e75bc'}
def initial_seventh_four(inputs,prior,current):
 p=inputs.get('initial_seventh_four')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('seventh four packet changed')
 if not prior or not current or p['prior_inventory_digest']!=digest(prior['inventory'])or p['current_extension_digest']!=digest(current):raise ValueError('seventh four prior changed')
 missing=sorted(r['symbol']for r in prior['inventory']if not r['has_timely_reading_facts'])
 if len(prior['inventory'])!=150 or missing[:4]!=CODES or p['selection']!=CODES or sum(r['has_timely_reading_facts']for r in prior['inventory'])!=66:raise ValueError('seventh four selection changed')
 fresh=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(fresh)or current['through']!='2026-11-19':raise ValueError('seventh four market changed')
 visual=p['visual_read']
 if visual!=VISUAL:raise ValueError('seventh four visual reading changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(p['sources'])!=10 or set(sources)!=set(IDS):raise ValueError('seventh four sources changed')
 for aid,s in sources.items():
  meta=s['raw_item']
  if s['sha256']!=SOURCE_SHA[aid]:raise ValueError('seventh four source SHA changed')
  pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!=IDS[aid]or s['symbol']!=IDS[aid]or re.sub('<[^>]+>','',meta['announcementTitle'])!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub>'2026-07-03'or not s['protected_gate_passed']:raise ValueError('seventh four identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('seventh four pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('seventh four page changed')
  from st_initial_warning_origin import origin_document_date
  if aid=='1225244457':
   if s['document_dated_on'] is not None or s.get('document_date_boundary')!='年报封面仅2026年4月，未确认整份文件落款日；采用正式披露日，报告期余额不作7月3日余额。':raise ValueError('seventh four annual date boundary changed')
  elif origin_document_date(s)!=s['document_dated_on']:raise ValueError('seventh four printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(t not in sources[aid]['selected_pages'][str(n)]for t in tokens):raise ValueError('seventh four risk/remediation clause changed')
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
   ss=[s for s in sources.values()if s['symbol']==r['symbol']];inventory.append({**r,'has_timely_reading_facts':True,'new_this_round':True,'latest_fact_on':max(s['published_on']for s in ss),'fact_ids':r['fact_ids']+['initial_seventh_four:'+s['announcement_id']for s in ss]})
  else:inventory.append({**r,'new_this_round':False})
 return {'anchor':'2026-07-03','through':'2026-11-19','title':'同样叫ST，风险和价格路径有什么不同？','intro':'百灵旧内控警示曾撤销，后因财报虚假记载再次ST；棕榈涉及连续亏损与持续经营，雪发摘星后仍有盈利和冻结约束，利源涉及财务共同条件及投资者诉讼。先分清剩余问题，再比较同窗表现。','window_note':'7月3日至11月19日，棕榈跌16.18%、百灵跌20.74%、利源跌23.74%、雪发跌29.40%，同窗ST整体跌19.88%、中证全指跌23.84%。百灵7月底尚略涨，全段转跌；短期修复不能外推。这组描述尚未识别各项风险或公告的净影响。','rows':rows,'inventory':inventory,'quote_audit':audit,'visual_read':visual,'counts':{'before':66,'after':70,'remaining':80,'members':150,'new_companies':4,'new_files':10,'new_pages':187},'selection_note':'从84家期初事实缺口按代码顺序取前四，不按事后收益筛选；非随机，也不声称前瞻盲选。','boundary':'只确认所选公告当时披露状态，不认证完整官方历史名录或所有警示条件。不同年份警示、财报与内控意见、诉请与赔偿、冻结与保证金分别核；年末余额不冒充期初余额。前复权同窗收益描述结果，不识别公告及制度净因果。','method_promotions':0,'full_membership_certification_added':False}
