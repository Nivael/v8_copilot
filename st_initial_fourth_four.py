"""Second code-ordered coverage batch; initial facts and later returns stay separate."""
from collections import Counter
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest
from st_initial_four import quote_audit
CODES=['002055', '002122', '002168', '002193']
IDS={'1225365570': '002055', '1225244280': '002055', '1225244262': '002055', '1225282697': '002168', '1225326146': '002193', '1225263624': '002193', '1225211734': '002193', '1225061216': '002168', '1224768534': '002122', '1224812570': '002122', '1225044690': '002055'}
CLAUSES={('1225365570', 1): ['变更保全标的物', '查封措施已解除'], ('1225365570', 2): ['四川省宜宾市中级人民法院', '子公司股权被冻结', '暂未收到法院下达的相关文书'], ('1225244280', 2): ['13,621.48', '2026年4月27日', '无保留意见审计报告'], ('1225244262', 1): ['2026年4月29日', '叠加实施其他风险警示'], ('1225244262', 2): ['持续经营重大不确定性', '2026年1月6日'], ('1225282697', 1): ['已获得深圳证券交易所核准', '2026年5月11日'], ('1225282697', 2): ['30,724.42', '1,599'], ('1225282697', 3): ['继续被实施其他风险警示', '不代表公司正式进入重整程序'], ('1225326146', 1): ['2026年5月22日', '行政处罚决定书'], ('1225326146', 5): ['作出行政处罚决定书之日起已满十二个月'], ('1225326146', 6): ['收到《行政处罚决定书》之日起满12个月'], ('1225263624', 1): ['2026年5月6日', 'ST如意'], ('1225211734', 3): ['300,537,937.39', '保留意见'], ('1225211734', 4): ['无法合理估计', '影响金额'], ('1225061216', 1): ['尚需获得深圳证券交易所核准'], ('1224768534', 1): ['2025年10月31日', '事先告知书'], ('1224812570', 1): ['2025年11月18日', '行政处罚决定书'], ('1224812570', 3): ['4,143.5948', '作出之日起满十二个月'], ('1225044690', 1): ['2026年3月27日', '行政处罚决定书']}
VISUAL=[{'announcement_id': '1225244280', 'page': 3, 'image_sha256': 'd5241fedeb70e8dc03c62c4cbfdd3d37d96ed32ac821f6fe4375ce01795d66b7', 'mode': 'manual_rendered_page', 'document_dated_on': '2026-04-27', 'note': '2025年4月14日完成工商变更，51.09万元4月27日现金回款；旧强调事项影响消除，2025年末内控标准无保留。'}]
DEFINITIONS=[{'symbol': '002055', 'primary': '1225244262', 'pages': [1, 2], 'risk_group': '旧内控修复，处罚与持续经营警示仍在', 'known_at_anchor': '旧内控强调事项已有审计师修复说明：以股抵债办理后，剩余51.09万元现金回款，2025年末内控为标准无保留；这不是全部资金均以现金收回。公司另有处罚类ST，并于3月27日收到最终处罚决定，4月29日起因连续亏损及持续经营疑虑叠加警示。6月同一大厦一项查封解除，另一法院却另有保全，不能笼统称资产全解封。', 'watch': '分别核每项警示的撤销条件，以及法院、案号、资产和保全范围；内控修复、最终处罚和某案解封不能互相替代。', 'supporting': [{'id': '1225244280', 'pages': [2, 3], 'note': '专项第3页为扫描页，已核原图：2025年4月14日完成工商变更、剩51.09万元4月27日现金回款，旧强调事项影响消除，2025年末内控标准无保留。文件落款2026年4月27日。'}, {'id': '1225044690', 'pages': [1, 5], 'note': '3月27日收到最终处罚决定，3月28日披露；不将收到或披露日当决定作出日推自动摘帽。'}, {'id': '1225365570', 'pages': [1, 2, 3], 'note': '璧山法院解除得润大厦查封，同时宜宾法院另有资产保全、子公司股权冻结增加；同一资产不同案件不能净成全面解封。'}]}, {'symbol': '002122', 'primary': '1224768534', 'pages': [1, 2], 'risk_group': '处罚类警示，财报更正不等于正式撤销', 'known_at_anchor': '2025年10月31日起因财报虚假记载被实施其他风险警示；11月18日已收到最终处罚决定，不能停留在事先告知。公司在11月公告称已更正并收到全部业绩补偿款约4143.59万元，但警示撤销仍有追溯重述、决定作出满十二个月及申请审核等条件，不能按收到日或自然周年自动摘帽。', 'watch': '核监管决定原件的作出日、对应整改与正式申请及生效日；补偿款是该事项披露，不当持续盈利或全部风险解除。', 'supporting': [{'id': '1224812570', 'pages': [1, 3, 4], 'note': '11月18日收到、19日披露最终决定；第3页称补偿款已付并列明作出日起十二个月及追溯重述条件，不以收到日自动推撤销。'}]}, {'symbol': '002168', 'primary': '1225282697', 'pages': [1, 2, 3], 'risk_group': '已撤销退市警示，仍有持续经营ST', 'known_at_anchor': '5月11日起已正式撤销退市风险警示，不再只写申请待审；2025年扣除后营收约3.07亿元、归母净资产1599万元，但仍亏损，财报为带持续经营重大不确定性段落的无保留意见，故继续ST。5月原件仍明确预重整备案不是法院正式受理，不能把摘星或投资协议当重整成功。', 'watch': '分别核持续经营条件、其他警示正式撤销，以及后续法院受理、重整计划和实际履约；本件只认证披露时点。', 'supporting': [{'id': '1225061216', 'pages': [1, 2, 6], 'note': '3月申请尚待核准的旧状态保留；与5月已核准、11日起生效的后件连接，不重复算两次修复。'}]}, {'symbol': '002193', 'primary': '1225263624', 'pages': [1, 2], 'risk_group': '处罚类ST与长期股权投资审计保留并存', 'known_at_anchor': '5月6日起因财报虚假记载实施ST，5月22日收到最终处罚决定。公司称相关历史报表已更正，但2025年审计仍保留：佛山莱卡出资及经营问题涉及约3亿元长期股权投资，审计师无法合理估计影响金额。历史更正不等于这项当前估值不确定性消失。', 'watch': '核正式决定作出日、对应整改、申请审核，以及被投资企业出资、经营和审计证据；不把投资账面额当已确认当期损失。', 'supporting': [{'id': '1225326146', 'pages': [1, 5, 6], 'note': '第5页引述规则从决定作出日起算，第6页公司计划却写收到日起满十二个月；保留原文差异，不据此计算自动摘帽日。5月22日是收到日，23日披露。'}, {'id': '1225211734', 'pages': [3, 4, 5], 'note': '财报保留基础为佛山莱卡长期股权投资及出资未履行，账面约3亿元；审计师称无法合理估计对财务状况和经营成果的影响金额，不能把账面额直接当损失。'}]}]
SOURCE_SHA={'1225365570': 'f04e07ab0d94cca8bf9f63f6e2cc6ae128c35b27ffd615e92f03089a78c40a3c', '1225244280': '99b8a5e5460429e83e23f1506e6aa683f5af8f54d5db0631dfd453dbef75cf55', '1225244262': 'd2d58a99b3afe6f7a41c23c278f96a343a7ab44c662e66fe85fe6c884bd5cfec', '1225282697': '26e30d86c04db4ee1ac73a18fd24b65ecd0472c94967df6a308380c17a9802a2', '1225326146': '470e6eb715338134d8d3979a54e6058c274064d3d7ece2c9a3e855c337d4c33d', '1225263624': '60fb3c2a7e3ce65d29a51711ad453b0c377b76571c2b77c40868adcb981d7922', '1225211734': 'd1058b86aa90dcad26c01a3c099c9ba303763da8f9e2ec5d134bd069f1935731', '1225061216': '066c6ce2b84f2bf296d266d9fe2d7210555b8c2649e1f9d90136f9279046d5f3', '1224768534': '3353f21320efab6815c62055ef2b2a5f921417a0d887faee015caced931e12bd', '1224812570': 'd5d60f93c6ca314aa1df1cb412222606da76e62bdf93dbdddc6b6923a40bfbb7', '1225044690': '13c5f0e01ba7198ab56982b59bdbbf6e0f20edcf309256088471f899ecf0823b'}
def initial_fourth_four(inputs,prior,current):
 p=inputs.get('initial_fourth_four')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('fourth four packet changed')
 if not prior or not current or p['prior_inventory_digest']!=digest(prior['inventory'])or p['current_extension_digest']!=digest(current):raise ValueError('fourth four prior changed')
 missing=sorted(r['symbol']for r in prior['inventory']if not r['has_timely_reading_facts'])
 if len(prior['inventory'])!=150 or missing[:4]!=CODES or p['selection']!=CODES or sum(r['has_timely_reading_facts']for r in prior['inventory'])!=54:raise ValueError('fourth four selection changed')
 fresh=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(fresh)or current['through']!='2026-11-19':raise ValueError('fourth four market changed')
 visual=p['visual_read']
 if visual!=VISUAL:raise ValueError('fourth four visual reading changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(p['sources'])!=11 or set(sources)!=set(IDS):raise ValueError('fourth four sources changed')
 for aid,s in sources.items():
  meta=s['raw_item']
  if s['sha256']!=SOURCE_SHA[aid]:raise ValueError('fourth four source SHA changed')
  pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!=IDS[aid]or s['symbol']!=IDS[aid]or re.sub('<[^>]+>','',meta['announcementTitle'])!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub>'2026-07-03'or not s['protected_gate_passed']:raise ValueError('fourth four identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('fourth four pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('fourth four page changed')
  if aid=='1225244280':
   if s['selected_pages']['3']!='' or s['document_dated_on']!='2026-04-27':raise ValueError('scan extraction/date changed')
  else:
   from st_initial_warning_origin import origin_document_date
   if origin_document_date(s)!=s['document_dated_on']:raise ValueError('fourth four printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(t not in sources[aid]['selected_pages'][str(n)]for t in tokens):raise ValueError('fourth four risk/remediation clause changed')
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
   ss=[s for s in sources.values()if s['symbol']==r['symbol']];inventory.append({**r,'has_timely_reading_facts':True,'new_this_round':True,'latest_fact_on':max(s['published_on']for s in ss),'fact_ids':r['fact_ids']+['initial_fourth_four:'+s['announcement_id']for s in ss]})
  else:inventory.append({**r,'new_this_round':False})
 return {'anchor':'2026-07-03','through':'2026-11-19','title':'修复了一项，为什么仍然是ST？','intro':'得润内控旧事项已有修复，惠程已正式摘星，但两者仍有其他警示；汇洲与如意的历史更正，也不能代替处罚类警示撤销。如意另有当前审计保留，得润不同法院的保全范围还需分别看。','window_note':'惠程5月已正式摘星，7月以来全段仍下跌26.70%；汇洲仍受处罚类警示约束，同窗却上涨5.49%。程序改善与股价上涨是两项不同结果；这四例用于保留反例，不推出普遍胜率。','rows':rows,'inventory':inventory,'quote_audit':audit,'visual_read':visual,'counts':{'before':54,'after':58,'remaining':92,'members':150,'new_companies':4,'new_files':11,'new_pages':50},'selection_note':'从96家期初事实缺口按代码顺序取前四，不按事后收益筛选；非随机，也不声称前瞻盲选。','boundary':'只确认各件当时披露状态，不认证所有风险解除、后续状态持续未变或完整官方历史名录。罚款、投资账面额与损益不混用；收到、作出、披露和正式撤销分别核。前复权同窗收益描述结果，不识别公告及制度净因果。扫描正文已看原图，文字提取边界保留。','method_promotions':0,'full_membership_certification_added':False}
