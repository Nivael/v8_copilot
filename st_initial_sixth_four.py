"""Sixth code-ordered coverage batch; initial facts and later returns stay separate."""
from collections import Counter
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest
from st_initial_four import quote_audit
CODES=['002217', '002227', '002306', '002323']
IDS={'1225379627': '002217', '1225133140': '002227', '1225133126': '002227', '1225363995': '002306', '1225092611': '002306', '1225251686': '002323'}
CLAUSES={('1225379627', 1): ['行政处罚事先告知书', '2026年6月23日'], ('1225379627', 2): ['作出行政处罚决定书之日起已满十二个月'], ('1225133126', 1): ['2.65亿元', '-0.67'], ('1225133140', 3): ['影响已消除'], ('1225133140', 4): ['193,298,777.70', '15,588,905.97'], ('1225363995', 1): ['2026年6月12日'], ('1225363995', 3): ['基本银行账户已解除冻结并新增一般银行账户冻结'], ('1225363995', 4): ['已获得深圳证券交易所审核同意'], ('1225092611', 4): ['尚需深交所批准'], ('1225251686', 1): ['三者均为负值', '2026年4月30日']}
VISUAL=[]
DEFINITIONS=[{'symbol': '002217', 'primary': '1225379627', 'pages': [1, 2, 3], 'risk_group': '财报虚假记载告知触发其他警示', 'known_at_anchor': '6月18日收到行政处罚事先告知书，涉及2017—2021年年报虚假记载；6月23日起实施其他风险警示。本件明确不触及重大违法强制退市情形，不把告知书当最终处罚决定。', 'watch': '分别核最终决定、追溯重述、正式申请及生效；不从告知日或ST开始日推自然周年自动撤销。', 'supporting': []}, {'symbol': '002227', 'primary': '1225133126', 'pages': [1, 2, 3], 'risk_group': '旧审计事项消除，新财务条件仍触发', 'known_at_anchor': '2024年审计保留涉及应收款及合同资产函证证据不足；4月专项已由会计师审核确认影响消除。但2025年扣除后营收约2.65亿元、归母亏损约0.67亿元，4月22日起仍新实施退市风险警示。旧证据修复不等于新年度财务条件达标。', 'watch': '跟踪同口径盈利和营收条件，以及实际回款；不能把函证证据补齐写成全部应收款现金收回。', 'supporting': [{'id': '1225133140', 'pages': [3, 4, 5, 6], 'note': '专项落款4月17日、披露4月21日；会计师确认旧保留事项影响消除。原应收账款193298777.70元、合同资产15588905.97元对应证据取得，不是同额现金到账。'}]}, {'symbol': '002306', 'primary': '1225363995', 'pages': [1, 2, 3, 4], 'risk_group': '已正式摘星，账户冻结仍使其继续ST', 'known_at_anchor': '6月12日起已正式撤销因财务指标及审计类型触发的退市和部分其他风险警示，不再只写4月申请待批。2025年扣除后营收约3.19亿元、归母净资产约7666万元，仍亏损；基本户已解冻却新增一般户冻结、相关诉讼未了，因此继续ST。', 'watch': '按账户与案件核剩余冻结及正式撤销；基本户解冻不等于全部账户解冻，摘星不等于盈利或彻底摘帽。', 'supporting': [{'id': '1225092611', 'pages': [1, 2, 3, 4], 'note': '4月11日披露旧申请及剩余银行账户冻结约束；与6月已核准生效连接，不重复算成两次独立修复。'}]}, {'symbol': '002323', 'primary': '1225251686', 'pages': [1, 2, 3], 'risk_group': '亏损与营收不足3亿元共同触发', 'known_at_anchor': '2025年利润总额、净利润与扣非净利润均负，扣除后营收低于3亿元，4月30日起实施退市风险警示。拓市场、改善周转和降低减值风险是整改计划，不能当已完成修复。', 'watch': '核新年度审计、盈利与营收共同条件及实际回款；不把条件性退市风险写成已经退市。', 'supporting': []}]
SOURCE_SHA={'1225379627': 'e63dd91ed839a68fa10a68bb06a5cb9e7df06d49d7ebd685b10e3a77b9a60c65', '1225133140': '74fc93858605fa542d324b3d03a05e99191a76e560ae98af43ef6df524f5ab10', '1225133126': 'e8445ba89579c4934293d0a9470f691bb1562d757467e8948743139e45805481', '1225363995': '4ac71a07198aee6cc045c59fe80fc2fa93fde844a6e23039e19d4b59039b8614', '1225092611': '24d452bf0a59964b80529aa7ef772948ff95250eb94a3bdc150deeacb59f61bf', '1225251686': '702f0f0e9546bb29632b7554f3643854793791d0327615cfffc8b6bb408ba7be'}
def initial_sixth_four(inputs,prior,current):
 p=inputs.get('initial_sixth_four')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('sixth four packet changed')
 if not prior or not current or p['prior_inventory_digest']!=digest(prior['inventory'])or p['current_extension_digest']!=digest(current):raise ValueError('sixth four prior changed')
 missing=sorted(r['symbol']for r in prior['inventory']if not r['has_timely_reading_facts'])
 if len(prior['inventory'])!=150 or missing[:4]!=CODES or p['selection']!=CODES or sum(r['has_timely_reading_facts']for r in prior['inventory'])!=62:raise ValueError('sixth four selection changed')
 fresh=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(fresh)or current['through']!='2026-11-19':raise ValueError('sixth four market changed')
 visual=p['visual_read']
 if visual!=VISUAL:raise ValueError('sixth four visual reading changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(p['sources'])!=6 or set(sources)!=set(IDS):raise ValueError('sixth four sources changed')
 for aid,s in sources.items():
  meta=s['raw_item']
  if s['sha256']!=SOURCE_SHA[aid]:raise ValueError('sixth four source SHA changed')
  pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!=IDS[aid]or s['symbol']!=IDS[aid]or re.sub('<[^>]+>','',meta['announcementTitle'])!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub>'2026-07-03'or not s['protected_gate_passed']:raise ValueError('sixth four identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('sixth four pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('sixth four page changed')
  from st_initial_warning_origin import origin_document_date
  if origin_document_date(s)!=s['document_dated_on']:raise ValueError('sixth four printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(t not in sources[aid]['selected_pages'][str(n)]for t in tokens):raise ValueError('sixth four risk/remediation clause changed')
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
   ss=[s for s in sources.values()if s['symbol']==r['symbol']];inventory.append({**r,'has_timely_reading_facts':True,'new_this_round':True,'latest_fact_on':max(s['published_on']for s in ss),'fact_ids':r['fact_ids']+['initial_sixth_four:'+s['announcement_id']for s in ss]})
  else:inventory.append({**r,'new_this_round':False})
 return {'anchor':'2026-07-03','through':'2026-11-19','title':'旧问题修好了，为什么仍然是ST？','intro':'特迅旧审计事项虽已消除，新年度亏损与营收条件仍触发退市风险警示；云网已正式摘星，却因银行账户冻结继续ST。合力泰是财报虚假记载告知触发，雅博是财务共同条件触发，修复范围与剩余约束分别看。','window_note':'云网已正式摘星、继续ST，7月3日至11月19日仍跌33.65%；雅博新受退市风险警示，同窗跌19.72%。这组反例不支持用单项程序改善预测收益，也不能反推风险越大表现越好；期间催化和大盘环境仍需分别核。','rows':rows,'inventory':inventory,'quote_audit':audit,'visual_read':visual,'counts':{'before':62,'after':66,'remaining':84,'members':150,'new_companies':4,'new_files':6,'new_pages':23},'selection_note':'从88家期初事实缺口按代码顺序取前四，不按事后收益筛选；非随机，也不声称前瞻盲选。','boundary':'只确认所选公告当时披露状态，不认证完整官方历史名录或所有警示条件。旧审计修复、新财务条件、不同账户冻结与最终处罚分别核；函证证据不是现金到账。前复权同窗收益描述结果，不识别公告及制度净因果。','method_promotions':0,'full_membership_certification_added':False}
