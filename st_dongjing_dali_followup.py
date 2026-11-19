"""Dated removal paths and financial reconciliation; no causal attribution."""
from decimal import Decimal as D
from hashlib import sha256
from canonical_json import digest
CODES=['002199','002214']
METRICS=['revenue','parent_profit','deducted_profit','operating_cash','parent_equity']
SOURCE_SHA={'1225421385': '0e4456c431263db2d41fb266926ef4a1745095264f56ebf229bcd664d1f336a4', '1225640094': '00e8ffc7690ca0d3afd4173358b74b51e9fc7c2d99c6db4ad0f5cf4519155025', '1225531390': '7758b83f0765606a68c772c07f02e9187f790a4922c8ce3e77cd716766a37a82', '1225423572': '26daa9ba601b2847133771acdf8d09eb1e3af3669000914d46611094aa834a19', '1225436048': 'f49d09fa8db9a597b1c84034d831760218b8793b6b5e53baecfa1c36ef75b49c', '1225456226': 'a7dc460824cf06c0a59a6c9092a9cdaad71a84b37170b9b1870a7503c616db83', '1225633260': 'f786d5466b04fb44c79ebabe72c0ed63a1fd9d164f93ba7bd805896e75252595', '1225633265': '6d12055cbf0c6b87a50a3d944fba62817028038b9b3a473504ab065125955595', '1225494051': '86e6aa813203d2420ee2741e09e5732a44f8efdd83634f987e9ac1066b109b66', '1225633264': '3fe8f5dd3e7e9828feb068a1c82c4f5eafd2a250a2113ddfc422daba718632b3'}
SOURCE_BINDINGS={'1225421385': {'symbol': '002199', 'url': 'https://static.cninfo.com.cn/finalpage/2026-07-14/1225421385.PDF', 'announcement_date': '2026-07-14', 'title': '2026年半年度业绩预告'}, '1225640094': {'symbol': '002214', 'url': 'https://static.cninfo.com.cn/finalpage/2026-10-30/1225640094.PDF', 'announcement_date': '2026-10-30', 'title': '2026年三季度报告'}, '1225531390': {'symbol': '002214', 'url': 'https://static.cninfo.com.cn/finalpage/2026-08-29/1225531390.PDF', 'announcement_date': '2026-08-29', 'title': '2026年半年度报告摘要'}, '1225423572': {'symbol': '002214', 'url': 'https://static.cninfo.com.cn/finalpage/2026-07-15/1225423572.PDF', 'announcement_date': '2026-07-15', 'title': '浙江大立科技股份有限公司2026年半年度业绩预告'}, '1225436048': {'symbol': '002199', 'url': 'https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-07-22/fc9df353-bb5a-49ac-82ea-820381a724cf.PDF', 'announcement_date': '2026-07-22', 'title': '*ST东晶：关于公司股票交易撤销退市风险警示暨股票停复牌的公告'}, '1225456226': {'symbol': '002214', 'url': 'https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-08-04/d7bb9c52-ce95-4147-bc1d-12c57efcf3d4.PDF', 'announcement_date': '2026-08-04', 'title': '*ST大立：浙江大立科技股份有限公司关于公司股票交易撤销退市风险警示暨停复牌的公告'}, '1225633260': {'symbol': '002199', 'url': 'https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-10-29/e9420d7c-aee2-4fa7-b1d3-c85c06fd9aa5.PDF', 'announcement_date': '2026-10-29', 'title': '东晶电子：2026年三季度报告'}, '1225633265': {'symbol': '002199', 'url': 'https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-10-29/c3242515-75a1-44d8-9ae3-29ce4835a8b9.PDF', 'announcement_date': '2026-10-29', 'title': '东晶电子：2026年半年度报告摘要（更正后）'}, '1225494051': {'symbol': '002199', 'url': 'https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-08-25/30ddaf42-4e1e-4651-947b-60a0f83fd951.PDF', 'announcement_date': '2026-08-25', 'title': '东晶电子：2026年半年度报告摘要'}, '1225633264': {'symbol': '002199', 'url': 'https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-10-29/75ab6f96-7889-4523-8ccb-b18d5e8ff1fa.PDF', 'announcement_date': '2026-10-29', 'title': '东晶电子：关于2026年半年度报告财务信息更正的公告'}}
def followup_view(inputs,prior,current):
 p=inputs.get('dongjing_dali_followup')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('followup packet changed')
 if not prior or p['prior_digest']!=digest(prior)or prior['counts']['after']!=62:raise ValueError('followup prior changed')
 m=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(m)or p['current_digest']!=digest(current):raise ValueError('followup market changed')
 sources={s['announcement_id']:s for s in p['sources']}
 if len(sources)!=10 or set(sources)!=set(SOURCE_SHA):raise ValueError('followup sources incomplete')
 for aid,s in sources.items():
  if {k:s[k]for k in SOURCE_BINDINGS[aid]}!=SOURCE_BINDINGS[aid]:raise ValueError('followup metadata changed')
  if s['sha256']!=SOURCE_SHA[aid]or not s['protected_gate_passed']or s['symbol']not in CODES or s['announcement_date']>'2026-11-19':raise ValueError('followup source identity changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('followup pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('followup page changed')
 def token(aid,n,t):
  if t not in sources[aid]['selected_pages'][str(n)]:raise ValueError('followup source clause changed')
 for aid,n,t in [('1225436048',1,'2026年7月23日'),('1225456226',1,'2026年8月5日'),('1225421385',1,'-2,000'),('1225423572',1,'-11,500'),('1225633264',2,'338,156,802.11'),('1225633264',2,'-14,304,120.70'),('1225640094',13,'公司第三季度财务会计报告未经审计')]:token(aid,n,t)
 e=next(r for r in inputs['strong_removal_cases']['rows']if r['symbol']=='002199')
 financial=p['financials'];east=financial['002199']
 if east!={k:e[k]for k in ['half','third','correction','reported_q3_single']}:raise ValueError('followup old financial history changed')
 dali=financial['002214']
 for period,aid in [('half','1225531390'),('third','1225640094')]:
  text=''.join(sources[aid]['selected_pages'].values())
  if dali[period]['published_on']!=sources[aid]['announcement_date']:raise ValueError('followup financial known date changed')
  for k in METRICS:
   if f'{D(dali[period][k]):,.2f}'not in text:raise ValueError('followup financial figure changed')
 single={k:str(D(dali['third'][k])-D(dali['half'][k]))for k in METRICS if k!='parent_equity'}
 if single!=dali['single_quarter']:raise ValueError('followup single quarter changed')
 for k in ['revenue','parent_profit','deducted_profit']:token('1225640094',1,f'{D(single[k]):,.2f}')
 cash=dali['cash']
 if sum(D(cash[k])for k in ['operating','investing','financing','fx'])!=D(cash['change'])or D(cash['opening'])+D(cash['change'])!=D(cash['closing'])or cash['operating']!=dali['third']['operating_cash']:raise ValueError('followup cash bridge changed')
 for k,val in cash.items():token('1225640094',12 if k=='operating'else 13,f'{D(val):,.2f}')
 from st_regime_comparison import build
 daily=build(m)['daily'];cal=[r['date']for r in daily];prices={(r['symbol'],r['trade_date']):r for r in m['fixed_prices']};bench={(r['benchmark_id'],r['trade_date']):D(str(r['close']))for r in m['benchmarks']};rows=[]
 for code in CODES:
  tr=next(r for r in inputs['member_transitions']['rows']if r['symbol']==code);resume=tr['effective_on'];idx=cal.index(resume);windows=[]
  for label,a,z in [('whole','2026-07-03','2026-11-19'),('first_resume_to_latest',resume,'2026-11-19')]+[(str(n)+'_after_resume',resume,cal[idx+n])for n in [5,20,40]if idx+n<len(cal)]:
   if not prices[(code,a)]['has_trade']or not prices[(code,z)]['has_trade']:raise ValueError('followup nontraded endpoint')
   stock=(D(str(prices[(code,z)]['close']))/D(str(prices[(code,a)]['close']))-1)*100;market=(bench[('csi_all_share',z)]/bench[('csi_all_share',a)]-1)*100;st=D(1);days=0
   for d in daily:
    if a<d['date']<=z:st*=1+D(str(d['return_pct']))/100;days+=1
   windows.append(dict(key=label,anchor=a,through=z,market_days=days,stock_pct=str(stock),market_pct=str(market),st_pct=str((st-1)*100)))
  reports=e if code=='002199'else dali
  quarter={k:str(D(reports['third'][k])-D(reports['half'][k]))for k in METRICS if k!='parent_equity'}
  rows.append({'symbol':code,'name':'东晶电子'if code=='002199'else'大立科技','announced_on':tr['announced_on'],'effective_on':resume,'windows':windows,'half':{k:reports['half'][k]for k in METRICS+['published_on']},'third':{k:reports['third'][k]for k in METRICS+['published_on']},'quarter':quarter})
 return {'through':'2026-11-19','title':'都摘帽了，短期强势为何没有走成同一种结果？','answer':'东晶复牌后的最初5日上涨更强，后来明显回落；大立起初平淡，较长窗口相对更强。两家公司后来都仍亏损，但盈利和现金改善的方向不同。程序解除、经营兑现与价格路径要分别追踪。','rows':rows,'sources':[{k:s[k]for k in ['announcement_id','symbol','title','url','announcement_date','sha256','pages']}for s in sources.values()],'counts':{'new_files':4,'new_pages':23,'reused_files':6,'reused_pages':33,'critical_pages_viewed':26,'windows':10,'initial_coverage':62},'boundary':'两家因全段结果相反而事后选取，非随机；等长事件窗的日历不同，不识别公告或制度净因果。复牌首日收盘为起点，不含首日涨跌。半年更正到10月29日才可知；三季报未经审计。期初覆盖仍62/150，无经验晋级。','method_promotions':0}
