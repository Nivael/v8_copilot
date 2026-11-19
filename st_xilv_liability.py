"""Supplement dated liability chains without rewriting the earlier Xilv timeline."""
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal as D
from hashlib import sha256
from canonical_json import digest

CHAINS=[
 ('old1000','funds','1000万元旧借款：已签展期','不是新增到账','2月借款5000万元中，4000万元已于5月归还；剩余1000万元先获展期批准，8月披露已签合同，年息3%、9个月。缓解到期压力，不等于新收1000万元。',[('1225435983',[1,4]),('1225462271',[1])]),
 ('quota','funds','1亿元额度内的5000万元展期','额度、批准、合同分开','8月提出最高1亿元循环额度，包含旧借款展期；9月7日股东会通过，28日签5000万元旧合同展期，年息3.5%、3个月。额度不是现金，展期本金也不能再加成新增流入。',[('1225487786',[1,4]),('1225552265',[2,3]),('1225588596',[1])]),
 ('guarantee','funds','子公司为购房人按揭提供担保','批准不等于已放款或代偿','扎尕那置业拟为购房人按揭提供1000万元阶段性连带责任保证，8月6日股东会通过。7月原件称尚未签协议，是否发生取决于贷款批准和取得；本批没有补到后续实际发生、解除或代偿证明。',[('1225435982',[1,2]),('1225462269',[3])]),
 ('execution','cases','旧施工纠纷：已查到执行信息','执行标的4570.88万元','扎尕那置业涉及甘肃建投土木工程建设集团的旧案，10月公告称从中国执行信息公开网查到被执行人信息、执行标的4570.8808万元；当时尚未收到法院文书。本批未独立取得执行系统记录和裁定，不能写成上市公司新增同额损失。',[('1225599714',[1,2])]),
 ('claim','cases','另一施工纠纷：仍处起诉阶段','本金与其他诉请分开','甘肃第六建设集团诉扎尕那置业，工程款本金约3994.90万元，另诉利息约336.84万元、违约金约183.03万元及其他费用。它与上条的原告不同，不能合成同一案件的进展；诉请不是判决或已确认损失。',[('1225603727',[1,2,3])]),
 ('cumulative','cases','累计1134万元：原被告方向不同','不与前期已披露金额重复相加','11月表列除前期已披露事项外的累计案件，含公司一方为原告和被告的案件；部分已完结，部分待开庭或执行。10月626.50万元的小额口径与本表范围变化未完全调节，不能直接算差额为新增案件或新增损失。',[('1225658225',[1,2,3])]),
]
CLAUSES={
 ('1225435983',1):['5月22日','4,000万元','剩余1,000万元'],('1225462271',1):['展期金额1,000万元','3.00%','9个月'],
 ('1225487786',1):['10,000万元','可循环使用且包含前期借款的展期'],('1225552265',2):['审议通过','借款额度'],('1225588596',1):['2026年9月28日','2026年6月25日','展期金额5,000万元','3.50%','3个月'],
 ('1225435982',2):['1,000万元','尚未与银行签订担保协议','贷款是否最终获批和取得','27,238.7万元','499.46%'],('1225462269',3):['审议通过','对外提供担保'],
 ('1225599714',1):['甘肃建投土木工程建设集团有限责任公司','中国执行信息公开网','45,708,808.00元','尚未收到'],
 ('1225603727',1):['起诉阶段','甘肃第六建设集团股份有限公司'],('1225603727',2):['39,948,967.53','3,368,363.78','1,830,341.91','626.50万元'],
 ('1225658225',1):['除前期已披露','1,134.00万元'],('1225658225',2):['影响存在不确定性'],('1225658225',3):['原告/申请人','被告/被申请人','58.13','332.98','81.19','507.5','154.20','979.80','1,134.00'],
}
FACTS={
 '1225435983':'7月原件回溯两笔实收5000万元及5月归还4000万元，就剩余1000万元申请展期；实际期限和利率仍待合同。',
 '1225462271':'公告称已签1000万元旧借款展期合同，年息3%、期限9个月；签约具体日仅写近日，不能由8月6日署期确定签约日。',
 '1225487786':'董事会通过最高1亿元循环借款额度，包含旧借款展期，尚需股东会审议；不是已借满或已到账。',
 '1225552265':'9月7日股东会通过向控股股东申请借款额度议案，公告9月8日披露；批准不等于提款。',
 '1225588596':'9月28日签署6月25日原内部借款合同展期，5000万元、年息3.5%、3个月，不是新借款现金流入。',
 '1225435982':'置业子公司拟为购房人按揭贷款提供1000万元阶段性连带保证；原件称尚未签银行协议，尚需股东会审议。',
 '1225462269':'8月6日股东会通过置业子公司对外提供担保议案；本件并未证明实际发放贷款、签订保证合同或发生代偿。',
 '1225599714':'公司公告转述执行公开网查询，旧施工案执行标的45,708,808.00元，当时尚未收到法院法律文书。',
 '1225603727':'另一原告甘肃第六建设集团诉置业子公司，仍处起诉阶段，工程款39,948,967.53元及另列利息、违约金与费用，损益影响不确定。',
 '1225658225':'除前期已披露事项外累计涉案1134万元，附表含原告和被告方向，损益影响不确定，不等于新增损失。',
}
DAYS={'1225435983':'2026-07-22','1225462271':'2026-08-07','1225487786':'2026-08-21','1225552265':'2026-09-08','1225588596':'2026-09-30','1225435982':'2026-07-22','1225462269':'2026-08-07','1225599714':'2026-10-10','1225603727':'2026-10-14','1225658225':'2026-11-05'}
def printed_date(s):
 from st_initial_warning_origin import origin_document_date
 return origin_document_date({**s,'pages':2 if s['announcement_id']=='1225658225'else s['pages']})
def xilv_liability(inputs,timeline):
 p=inputs.get('xilv_liability')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'})or not timeline or p['timeline_digest']!=digest(timeline):raise ValueError('xilv liability binding changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if set(sources)!=set(DAYS)or len(p['sources'])!=10:raise ValueError('xilv liability source set changed')
 for aid,s in sources.items():
  meta=s['raw_item'];day=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if meta['secCode']!='000610'or s['symbol']!='000610'or str(meta['announcementId'])!=aid or s['title']!=meta['announcementTitle']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or day!=DAYS[aid]or s['published_on']!=day or not s['protected_gate_passed']:raise ValueError('xilv liability identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('xilv liability pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('xilv liability page changed')
  if printed_date(s)!=s['document_dated_on']:raise ValueError('xilv liability printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(t not in sources[aid]['selected_pages'][str(n)]for t in tokens):raise ValueError('xilv liability stage/amount changed')
 path={r['date']:r for r in timeline['path']};dates=sorted(path)
 def window(pub,n):
  anchor=max(d for d in dates if d<pub);future=[d for d in dates if d>=pub];base={'anchor':anchor,'requested_days':n,'available_days':len(future),'complete':len(future)>=n}
  if len(future)<n:return {**base,'through':None,'stock_pct':None,'st_pct':None,'market_pct':None}
  end=future[n-1];a,z=path[anchor],path[end];calc=lambda x,y:float((D(str(y))/D(str(x))-1)*100)
  return {**base,'through':end,'stock_pct':calc(a['stock_close'],z['stock_close']),'st_pct':calc(1+D(str(a['st_pct']))/100,1+D(str(z['st_pct']))/100),'market_pct':calc(1+D(str(a['market_pct']))/100,1+D(str(z['market_pct']))/100)}
 public=lambda s:{k:v for k,v in s.items()if k not in ['raw_item','selected_pages','page_hashes']}
 chains=[]
 for key,group,title,status,reading,refs in CHAINS:
  steps=[{'source':public(sources[aid]),'fact':FACTS[aid],'pages':pages,'windows':[window(DAYS[aid],n)for n in [1,5,20]]}for aid,pages in refs]
  chains.append({'key':key,'group':group,'title':title,'status':status,'reading':reading,'steps':steps})
 requests=[D('39948967.53'),D('3368363.78'),D('1830341.91')];big=[D(x)for x in ['58.13','332.98','81.19','507.5']];total=sum(big)+D('154.20')
 if sum(big)!=D('979.80')or total!=D('1134.00'):raise ValueError('xilv litigation arithmetic changed')
 return {'through':timeline['through'],'chains':chains,'arithmetic':{'claim_principal_yuan':str(requests[0]),'claim_interest_yuan':str(requests[1]),'claim_penalty_yuan':str(requests[2]),'claim_requested_sum_excluding_other_costs_yuan':str(sum(requests)),'cumulative_large_cases_wanyuan':str(sum(big)),'cumulative_other_cases_wanyuan':'154.20','cumulative_total_wanyuan':str(total),'not_recognized_losses':True},'counts':{'new_files':10,'new_pages':sum(s['pages']for s in sources.values()),'chains':6,'source_disclosures':10,'complete_windows':sum(w['complete']for c in chains for s in c['steps']for w in s['windows']),'incomplete_windows':sum(not w['complete']for c in chains for s in c['steps']for w in s['windows'])},'judgment':'资金支持已有实质展期，但不能当新增现金；担保、起诉与执行风险并存。原“进展不等于风险解除”得到支持，借款解释须补入两笔旧债展期和额度批准。','boundaries':['各状态只到原件披露日，不据此认证11月19日余额、是否代偿或法院最新阶段。','旧1000万元与6月合同5000万元是两条不同借款链；额度、展期和上一轮首期经营借款不能相加当新增到账。','担保主体是扎尕那置业、被担保人为购房者，不是上市公司收到同额银行贷款。','执行案原始法院文书和执行系统记录尚未独立取得；诉请、执行标的与会计损失分别保留。','累计诉讼范围排除前期已披露事项，小额口径未完全调节，不认证新增净损失或期间全部案件。','同链重复文件及重叠窗口不是独立经验验证；披露时刻未知，窗口只作事后描述。'],'method_promotions':0}
