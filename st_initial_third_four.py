"""Second code-ordered coverage batch; initial facts and later returns stay separate."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest
from st_initial_four import quote_audit
CODES=['000838', '000903', '000911', '002024']
IDS={'1225400676': '000838', '1225170536': '000838', '1225212391': '000903', '1225212355': '000903', '1225389952': '000911', '1225245896': '000911', '1225346702': '002024', '1225064494': '002024', '1225212367': '000903', '1225388521': '002024'}
CLAUSES={('1225170536', 1): ['-200,131,538.18', '282,155,640.42'], ('1225400676', 2): ['仍未获债权人会议通过', '重整投资协议已解除', '不同主体'], ('1225212391', 1): ['2024年度', '影响已消除'], ('1225212355', 1): ['2026年4月28日', '叠加实施其他风险警示'], ('1225389952', 2): ['未发现', '重大会计差错'], ('1225389952', 3): ['无保留意见的内部控制审计报告'], ('1225245896', 1): ['净资产为负值', '否定意见', '2026年4月30日'], ('1225346702', 7): ['68,953', '40%', '60%'], ('1225346702', 8): ['1.2亿元', '逐步确认', '尚需提交公司股东会审议'], ('1225388521', 1): ['2026年6月25日'], ('1225388521', 4): ['关于债务和解的议案', '99.28%'], ('1225064494', 2): ['2023年度、2024年度、2025年度', '2026年3月31日']}
VISUAL=[{'announcement_id': '1225212367', 'page': 2, 'image_sha256': '78fc1d85151f8318b506ffb157a177496d6724204ff3033d2bb8d903e925f886', 'mode': 'manual_rendered_page', 'note': '财报2025年为带持续经营重大不确定性段落的无保留意见；三年扣非归母亏损。'}, {'announcement_id': '1225212367', 'page': 3, 'image_sha256': '90143c3ec20fe8574a3977b4d79ea20855bb3e557640a477e7c32bb9a4fdbd7e', 'mode': 'manual_rendered_page', 'note': '回顾2024年立案未决的强调事项，不是2025年仍未收到处罚决定。'}, {'announcement_id': '1225212367', 'page': 4, 'image_sha256': '1b57065876c39bf71567360b00d6c38aba2a7b36add8b27d5d298b9151f15758', 'mode': 'manual_rendered_page', 'note': '2025年8月8日收到处罚决定，8月12日会计差错更正；专项称旧强调事项影响已消除。'}, {'announcement_id': '1225212367', 'page': 5, 'image_sha256': 'fb5b48d77fe95125b66908676086ef03b1c2cfbe77d9cf825b53c6dca0959b18', 'mode': 'manual_rendered_page', 'note': '专项签章页，文件落款2026年4月24日。'}]
DEFINITIONS=[{'symbol': '000838', 'primary': '1225170536', 'pages': [1, 2], 'risk_group': '亏损收入门槛与负净资产，股东重整另核', 'known_at_anchor': '2025年归母净资产约负2亿元、扣除后营收约2.82亿元且扣非亏损，另有三年亏损与持续经营疑虑，4月27日起实施警示。7月1日披露控股股东等13家公司重整草案再次未获通过、投资协议解除；这不是上市公司自身重整失败。', 'watch': '上市公司财务修复、控股股东程序及股份冻结分别核；公司关于日常经营影响的表述不作为无风险保证。', 'supporting': [{'id': '1225400676', 'pages': [1, 2, 3], 'note': '披露7月1日，落款6月30日；股东重整草案再次未通过，投资协议解除。上市公司、控股股东与间接控股股东不是同一主体。'}]}, {'symbol': '000903', 'primary': '1225212355', 'pages': [1, 2], 'risk_group': '旧强调事项消除，新持续经营警示叠加', 'known_at_anchor': '2024年报立案未决的强调事项有修复说明；审计师专项明确2025年8月已收到处罚决定并作差错更正，不能把回顾旧立案状态写成当前仍未决。但2025年财报仍为带持续经营重大不确定性段落的无保留意见，三年扣非前后孰低亏损，4月28日起叠加其他警示，另保留原处罚类警示。', 'watch': '旧强调事项消除、处罚类警示撤销条件和新持续经营约束分别核；没有据单项消除认证正式撤销全部ST。', 'supporting': [{'id': '1225212391', 'pages': [1], 'note': '审计委员会称2024年报强调事项影响已消除；是本件的判断范围，不等于全部警示解除。'}, {'id': '1225212367', 'pages': [2, 3, 4, 5], 'note': '专项正文为扫描页，已逐页核对原图：第2页讲2025持续经营，第3至4页回顾旧立案到处罚和整改，末页落款4月24日；正文文字提取仍有限。'}]}, {'symbol': '000911', 'primary': '1225245896', 'pages': [1, 2], 'risk_group': '负净资产、持续经营与内控否定同时存在', 'known_at_anchor': '4月30日起因负净资产被实施退市风险警示，同时有连续亏损与持续经营疑虑、内控否定意见的其他警示。6月27日披露成立整改组、完善制度和内部检查等措施；内部自查未发现重大差错不等于取得无保留内控审计或正式撤销。', 'watch': '年度净资产、持续经营和内控意见逐项核；整改措施、自查与外部审计、正式撤销分别保留。', 'supporting': [{'id': '1225389952', 'pages': [1, 2, 3], 'note': '进展同时保留三类约束。公司自查与整改披露不是审计师已出无保留内控意见；本件列明申请撤销所需意见。'}]}, {'symbol': '002024', 'primary': '1225064494', 'pages': [1, 2], 'risk_group': '持续经营警示仍在，债务和解分阶段兑现', 'known_at_anchor': '公司2023至2025年扣非前后净利润孰低均为负、2025财报有持续经营重大不确定性，继续ST。6月3日债务和解方案预计豁免68953万元，收益确认随协议和分期支付；6月25日股东会已通过该议案，不应继续写成股东会待审。证券持有人会议、正式签署履约与实际收益仍不能由这次股东会代替。', 'watch': '分别核另一侧审批、正式协议、分期支付与经审计确认；豁免总额不等于当期利润或已到账现金。', 'supporting': [{'id': '1225346702', 'pages': [1, 7, 8, 9], 'note': '6月初方案：40%分期支付、60%分期豁免；预计豁免68953万元，签约后违约金等一次性收益初估1.2亿元，其他随支付确认，不合并当期。'}, {'id': '1225388521', 'pages': [1, 4], 'note': '6月25日股东会召开，6月26日披露提案6.00通过；关闭公司股东会待审，不证明持有人会议通过、正式履约或全部收益已确认。'}]}]
SOURCE_SHA={'1225400676': '7e59dc7f548312f693e99fcca11898fb3e938b0fe0670f8ebcd43511fefdb778', '1225170536': 'fe13c9edb1828d473e394985fab77c73b2c78fda1f835298bc06b34fe8d4828a', '1225212391': 'f70637db54056887301bff7b9bdea4e3cbec54f2293d1d1705edea5a4e75a986', '1225212355': '2ef3e4d2cc7d1dc4857315a49154782dfcc5b1783fbfb81ec6bfcfd9e02cce4c', '1225389952': '4da105a0af8c2684dc3e5db52c827a2ab9bc7a8738f5fe995f4ff1e5ab3d646e', '1225245896': '6589dc9b8001bcf09472a1de66d94fd98fbe7ed3ef18418925991c77f1e60d1c', '1225346702': '5af3861ed04004c014aa7385558dcb36f8d52db110aba1262e2749799ec2653b', '1225064494': '04187c63cd9bb2117d0e9982d83755a85ec9369134e0f37f8355e933f67c25c9', '1225212367': '733548b23c68c79df5bcc0c29779584648f7cdae39c4f7922425c8dc5a3f5491', '1225388521': '35f57a44f5ea72c6fc042ff4bfda212a245bcccc4823acdb8c964baf6bcb2fb9'}

def initial_third_four(inputs,prior,current):
 p=inputs.get('initial_third_four')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('third four packet changed')
 if not prior or not current or p['prior_inventory_digest']!=digest(prior['inventory'])or p['current_extension_digest']!=digest(current):raise ValueError('third four prior changed')
 missing=sorted(r['symbol']for r in prior['inventory']if not r['has_timely_reading_facts'])
 if len(prior['inventory'])!=150 or missing[:4]!=CODES or p['selection']!=CODES or sum(r['has_timely_reading_facts']for r in prior['inventory'])!=50:raise ValueError('third four selection changed')
 fresh=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(fresh)or current['through']!='2026-11-19':raise ValueError('third four market changed')
 visual=p['visual_read']
 if visual!=VISUAL:raise ValueError('third four visual reading changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(p['sources'])!=10 or set(sources)!=set(IDS):raise ValueError('third four sources changed')
 for aid,s in sources.items():
  meta=s['raw_item']
  if s['sha256']!=SOURCE_SHA[aid]:raise ValueError('third four source SHA changed')
  pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!=IDS[aid]or s['symbol']!=IDS[aid]or meta['announcementTitle']!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub>'2026-07-03'or not s['protected_gate_passed']:raise ValueError('third four identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('third four pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('third four page changed')
  if aid=='1225212367':
   if any(s['selected_pages'][str(n)] for n in [2,3,4,5]) or s['document_dated_on']!='2026-04-24':raise ValueError('scan extraction/date changed')
  else:
   from st_initial_warning_origin import origin_document_date
   if origin_document_date(s)!=s['document_dated_on']:raise ValueError('third four printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(t not in sources[aid]['selected_pages'][str(n)]for t in tokens):raise ValueError('third four risk/remediation clause changed')
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
   ss=[s for s in sources.values()if s['symbol']==r['symbol']];inventory.append({**r,'has_timely_reading_facts':True,'new_this_round':True,'latest_fact_on':max(s['published_on']for s in ss),'fact_ids':r['fact_ids']+['initial_third_four:'+s['announcement_id']for s in ss]})
  else:inventory.append({**r,'new_this_round':False})
 return {'anchor':'2026-07-03','through':'2026-11-19','title':'旧事项消除、整改与和解，哪些条件仍未兑现？','intro':'发展涉及股东重整，云动旧强调事项消除仍有新警示，广糖有整改但约束未解除，易购股东会通过也不等于和解履约。把期初已知状态与后续窗口放在一起，单一ST标签不足以解释分化。','window_note':'发展最初20日上涨41.24%，到11月19日却较同一起点下跌32.20%；广糖全段接近平盘。短期上涨没有保证长期延续，整改披露也不能代替正式风险解除；两种现象都要结合后续公告继续解释。','rows':rows,'inventory':inventory,'quote_audit':audit,'visual_read':visual,'counts':{'before':50,'after':54,'remaining':96,'members':150,'new_companies':4,'new_files':10,'new_pages':42},'selection_note':'从100家期初事实缺口按代码顺序取前四，不按事后收益筛选；非随机，也不声称前瞻盲选。','boundary':'只确认各件当时披露状态，不认证全部风险解除、之后持续未变或完整官方名录。前复权同窗涨跌描述结果，不分摊公告或制度净因果；扫描页逐页视觉核对，正文文字提取仍有限。','method_promotions':0,'full_membership_certification_added':False}
