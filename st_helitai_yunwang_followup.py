"""Case-specific updates; repeated notices and arithmetic conflicts remain explicit."""
from decimal import Decimal as D
from hashlib import sha256
from canonical_json import digest
SOURCE_BINDINGS={'1225612250': {'symbol': '002217', 'url': 'https://static.cninfo.com.cn/finalpage/2026-10-21/1225612250.PDF', 'published_on': '2026-10-21', 'document_dated_on': '2026-10-20', 'sha256': '6602b6ceeea1675ddc6de71dd95f3c47f8607854d4e97189530d6c1dbc3ba290', 'title': '关于公司股票交易被实施其他风险警示相关事项的进展公告'}, '1225564828': {'symbol': '002217', 'url': 'https://static.cninfo.com.cn/finalpage/2026-09-16/1225564828.PDF', 'published_on': '2026-09-16', 'document_dated_on': '2026-09-15', 'sha256': '5bb78872061bf5987fe058db2d64bcdd372150a8ef6c3f44de103d28ac2ee10e', 'title': '关于公司股票交易被实施其他风险警示相关事项的进展公告'}, '1225474469': {'symbol': '002217', 'url': 'https://static.cninfo.com.cn/finalpage/2026-08-15/1225474469.PDF', 'published_on': '2026-08-15', 'document_dated_on': '2026-08-14', 'sha256': '8bbc04d14bd9011a211d54cd50493b8acf79e30dff4a6e61f37fab123717f271', 'title': '关于公司股票交易被实施其他风险警示相关事项的进展公告'}, '1225430291': {'symbol': '002217', 'url': 'https://static.cninfo.com.cn/finalpage/2026-07-18/1225430291.PDF', 'published_on': '2026-07-18', 'document_dated_on': '2026-07-17', 'sha256': '08e130a62bcd7701cadcde5539a805948f2f1d64d497f22502889c3667cb0032', 'title': '关于公司股票交易被实施其他风险警示相关事项的进展公告'}, '1225669041': {'symbol': '002306', 'url': 'https://static.cninfo.com.cn/finalpage/2026-11-13/1225669041.PDF', 'published_on': '2026-11-13', 'document_dated_on': '2026-11-13', 'sha256': '9e838690d90cfd1302f0a0e822d6e75bb27342983b510fc868bfa1d83abfe6cf', 'title': '关于相关诉讼案件的进展公告'}, '1225619169': {'symbol': '002306', 'url': 'https://static.cninfo.com.cn/finalpage/2026-10-26/1225619169.PDF', 'published_on': '2026-10-26', 'document_dated_on': '2026-10-26', 'sha256': '28e0aa57b2522f2978ce29773545c50dfdb633642514b02a3fc1c6c02ed51166', 'title': '相关诉讼公告'}, '1225586937': {'symbol': '002306', 'url': 'https://static.cninfo.com.cn/finalpage/2026-09-30/1225586937.PDF', 'published_on': '2026-09-30', 'document_dated_on': '2026-09-30', 'sha256': '9e9b8f1b6e37f8bd27668fc6320e71ba5b321300bdf56fe3c252b25c9d65ecfe', 'title': '关于相关诉讼案件的进展公告'}, '1225489602': {'symbol': '002306', 'url': 'https://static.cninfo.com.cn/finalpage/2026-08-22/1225489602.PDF', 'published_on': '2026-08-22', 'document_dated_on': '2026-08-22', 'sha256': '25063a2552be5d64d49a4cf3f7340620392399dd620dc146efec64edd9bef171', 'title': '关于相关诉讼案件的进展公告'}}
CHAINS=[{'key': 'rent', 'entity': 'listed_company', 'changes': [{'published_on': '2026-08-22', 'aid': '1225489602', 'page': 2, 'state': '调解约定支付31.95万元，不认证本件时已经付足或解冻'}, {'published_on': '2026-09-30', 'aid': '1225586937', 'page': 2, 'state': '已足额支付和解金额，对应涉诉银行账号已解冻；只关闭该案付款及对应账户待办'}]}, {'key': 'lead_intelligent', 'entity': 'subsidiary', 'changes': [{'published_on': '2026-08-22', 'aid': '1225489602', 'page': 2, 'state': '无锡先导撤诉，未认证实体争议永久消除或账户解冻'}, {'published_on': '2026-09-30', 'aid': '1225586937', 'page': 2, 'state': '收到重新起诉文件，诉讼标的仍1248.72万元'}]}, {'key': 'construction', 'entity': 'listed_company_and_subsidiary', 'changes': [{'published_on': '2026-09-30', 'aid': '1225586937', 'page': 1, 'state': '二审驳回上诉、维持原判；公司披露半年已计提预计负债256.30万元，不当本件新增同额损失'}, {'published_on': '2026-11-13', 'aid': '1225669041', 'page': 2, 'state': '众鑫实业已申请执行；不认证已实际划款或执行完毕'}]}, {'key': 'convertible_loan', 'entity': 'listed_company_and_subsidiary', 'changes': [{'published_on': '2026-11-13', 'aid': '1225669041', 'page': 1, 'state': '扬州科创基金案收到民事调解书，剩余本金2200万元，约定按时支付；不当已清偿'}]}, {'key': 'new_purchase_claim', 'entity': 'listed_company_and_controller', 'changes': [{'published_on': '2026-11-13', 'aid': '1225669041', 'page': 2, 'state': '抚州安通买卖合同起诉2215.69万元，公司称实欠货款999.96万元，尚未开庭；诉请、公司披露欠款与损益不合并'}]}, {'key': 'new_loan_claim', 'entity': 'listed_company', 'changes': [{'published_on': '2026-10-26', 'aid': '1225619169', 'page': 2, 'state': '高邮兴区建设借款诉讼请求本金4900万元另加息罚，已受理未开庭；叙述段原印为4.900万元，与摘要和诉请4900万元表述不同，原文保留，不自行更正或当4900万元损失'}]}, {'key': 'robot_closed', 'entity': 'subsidiary', 'changes': [{'published_on': '2026-10-26', 'aid': '1225619169', 'page': 3, 'state': '蓝海机器人453万元案件收到结案通知，不扩大为全部诉讼结束或全部账户解冻'}]}]
FREEZE_ROWS=[{'entity': 'listed_company', 'account_suffix': '6823', 'amount': '6773434.50', 'page': 2}, {'entity': 'listed_company', 'account_suffix': '6823', 'amount': '2155535.00', 'page': 2}, {'entity': 'listed_company', 'account_suffix': '6823', 'amount': '247200.00', 'page': 2}, {'entity': 'listed_company', 'account_suffix': '6823', 'amount': '41200.00', 'page': 3}, {'entity': 'listed_company', 'account_suffix': '6823', 'amount': '103000.00', 'page': 3}, {'entity': 'subsidiary', 'account_suffix': '0564', 'amount': '2155535.00', 'page': 3}]
CLAUSES={('1225669041',1):['民事调解书','2,200万元'],('1225669041',2):['申请执行','2,215.69万元','999.96万元','尚未开庭'],('1225619169',1):['4,900万元','尚未开庭'],('1225619169',2):['4.900万元','4,900万元'],('1225619169',3):['结案通知书'],('1225586937',1):['驳回上诉,维持原判'],('1225586937',2):['足额支付和解金额','银行账号已解除冻结','重新起诉'],('1225586937',3):['9,320,369.50','2,155,535.00'],('1225489602',2):['31.95万元','无锡先导撤回起诉','江松科技撤回起诉']}
def freeze_audit(rows,reported):
 total=sum(D(r['amount'])for r in rows);parent=sum(D(r['amount'])for r in rows if r['entity']=='listed_company');reported=D(reported)
 return {'rows':rows,'row_sum_yuan':str(total),'reported_subtotal_yuan':str(reported),'difference_yuan':str(total-reported),'parent_only_sum_yuan':str(parent),'unresolved':True,'certified_total_yuan':None,'not_loss':True}
def followup_view(inputs,prior,current):
 p=inputs.get('helitai_yunwang_followup')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('case followup packet changed')
 if not prior or p['prior_digest']!=digest(prior)or prior['counts']['after']!=66 or p['current_digest']!=digest(current):raise ValueError('case followup prior changed')
 m=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(m):raise ValueError('case followup market changed')
 ss={s['announcement_id']:s for s in p['sources']}
 if len(p['sources'])!=8 or set(ss)!=set(SOURCE_BINDINGS):raise ValueError('case followup sources incomplete')
 for aid,s in ss.items():
  if {k:s[k]for k in SOURCE_BINDINGS[aid]}!=SOURCE_BINDINGS[aid]or not s['protected_gate_passed']:raise ValueError('case followup source metadata changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('case followup pages incomplete')
  for n,text in s['selected_pages'].items():
   if sha256(text.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('case followup page changed')
  from st_initial_warning_origin import origin_document_date
  if origin_document_date(s)!=s['document_dated_on']:raise ValueError('case followup printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(token not in ss[aid]['selected_pages'][str(n)]for token in tokens):raise ValueError('case followup stage clause changed')
 updates=[]
 for s in ss.values():
  if s['symbol']=='002217':
   if '最终结果将以福建证监局出具的《行政处罚决定书》为准'not in s['selected_pages']['1']:raise ValueError('penalty stage changed')
   updates.append({'aid':s['announcement_id'],'published_on':s['published_on'],'document_dated_on':s['document_dated_on'],'independent_remediation_added':0})
 if len(updates)!=4:raise ValueError('repeated update count changed')
 if p['freeze_rows']!=FREEZE_ROWS:raise ValueError('freeze scope changed')
 for r in p['freeze_rows']:
  if f"{D(r['amount']):,.2f}"not in ss['1225586937']['selected_pages'][str(r['page'])]:raise ValueError('freeze amount changed')
 if p['reported_subtotal_yuan']!='9320369.50':raise ValueError('reported subtotal changed')
 conflict=freeze_audit(p['freeze_rows'],p['reported_subtotal_yuan'])
 from st_regime_comparison import build
 daily=build(m)['daily'];cal=['2026-07-03']+[d['date']for d in daily];prices={(r['symbol'],r['trade_date']):r for r in m['fixed_prices']};bench={(r['benchmark_id'],r['trade_date']):D(str(r['close']))for r in m['benchmarks']};events=[]
 for aid in ['1225489602','1225586937','1225619169','1225669041']:
  pub=ss[aid]['published_on'];a=max(d for d in cal if d<pub);idx=cal.index(a);wins=[]
  for n in [1,5,20]:
   available=len(cal)-1-idx;z=cal[min(idx+n,len(cal)-1)]
   if not prices[('002306',a)]['has_trade']or not prices[('002306',z)]['has_trade']:raise ValueError('case followup nontraded endpoint')
   stock=(D(str(prices[('002306',z)]['close']))/D(str(prices[('002306',a)]['close']))-1)*100;market=(bench[('csi_all_share',z)]/bench[('csi_all_share',a)]-1)*100;st=D(1);days=0
   for d in daily:
    if a<d['date']<=z:st*=1+D(str(d['return_pct']))/100;days+=1
   wins.append({'requested_days':n,'observed_days':days,'anchor':a,'through':z,'status':'complete'if available>=n else'unfinished','stock_pct':str(stock),'market_pct':str(market),'st_pct':str((st-1)*100)})
  events.append({'aid':aid,'published_on':pub,'windows':wins})
 return {'through':'2026-11-19','title':'一案付款解冻了，为什么还不能说风险已解除？','answer':'云网有一宗租赁案已付款、对应账户已解冻，但同时出现新的基本户冻结、撤诉后重新起诉、申请执行和新诉讼。应按案件关闭或重新打开待办，不能用一项改善概括全部风险。合力泰四次月度进展仍是一条未完成事项。','chains':CHAINS,'freeze_conflict':conflict,'helitai_updates':sorted(updates,key=lambda r:r['published_on']),'event_windows':events,'sources':[{k:s[k]for k in ['announcement_id','symbol','title','url','published_on','document_dated_on','sha256','pages']}for s in ss.values()],'counts':{'files':8,'pages':21,'viewed_pages':21,'chains':len(CHAINS),'complete_windows':sum(w['status']=='complete'for e in events for w in e['windows']),'unfinished_windows':sum(w['status']=='unfinished'for e in events for w in e['windows']),'initial_coverage':66},'boundary':'正式目录日与落款分开；合力泰最近所核进展披露10月21日、落款10月20日，不认证此后所有渠道均无新决定。公告日前一市场日收盘为基准，不认证最早反应或公告净因果。冻结表口径未澄清，不选择最终合计；诉请、欠款、冻结与损失不混用。期初覆盖不变，无经验晋级。','method_promotions':0}
