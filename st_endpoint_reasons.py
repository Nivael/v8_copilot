"""Explain frozen endpoint gaps using already verified issuer stages, without imputing returns."""
from canonical_json import digest
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
import re
CODES=['000016','002717','002731','600491']
IDS={'1225545707','1225605494','1225615607','1225607488','1225602315','1225609701','1225669888','1225407586','1225417943'}
CLAUSES={('1225545707',1):['2026年9月4日','停牌'],('1225605494',2):['989,276,152','已完成交收'],('1225615607',1):['2026年10月16日','2026年10月23日','主动'],('1225607488',2):['2026年5月6日','2026年7月7日'],('1225602315',1):['2026年10月13日','不进入退市整理期'],('1225609701',1):['2026年10月16日','事先告知','拟决定','听证'],('1225669888',1):['2026年11月12日','2026年11月13日'],('1225407586',1):['2026年7月3日','筹划'],('1225417943',1):['2026年7月3日至2026年7月9日','2026/7/10']}
def endpoint_reasons(inputs,current,integrity,halts):
 p=inputs.get('endpoint_reasons')
 if p is None:return None
 if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('endpoint reasons packet changed')
 if not all([current,integrity,halts])or p['current_digest']!=digest(current)or p['integrity_digest']!=digest(integrity)or p['halt_digest']!=digest(halts)or current['through']!='2026-11-19':raise ValueError('endpoint reasons prior changed')
 m=inputs['current_extension']['market_inputs']
 if p['market_digest']!=digest(m):raise ValueError('endpoint reasons market changed')
 known={s['announcement_id']:s for s in inputs['sample_integrity']['primary_sources']+inputs['halt_stages']['sources']+inputs['current_extension']['sources']};sources={s['announcement_id']:s for s in p['sources']}
 if set(sources)!=IDS or len(p['sources'])!=9:raise ValueError('endpoint reasons sources changed')
 for aid,s in sources.items():
  k=known[aid];pub=k.get('published_on',k.get('announcement_date'))
  if s['sha256']!=k['sha256']or s['title']!=k['title']or s['url']!=k['url']or s['symbol']!=k['symbol']or s['published_on']!=pub or not s['protected_gate_passed']or s['original_observed_at']!=k['observed_at']or s['reused']is not True:raise ValueError('endpoint reasons reused identity changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('endpoint reasons pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('endpoint reasons page changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(token not in sources[aid]['selected_pages'][str(n)]for token in tokens):raise ValueError('endpoint reasons stage clause changed')
 cat=p['catalog'];rows=cat['rows']
 if cat['symbol']!='002717'or cat['total']!=34 or len(rows)!=34 or len({r['announcement_id']for r in rows})!=34 or any(r['symbol']!='002717'or not '2026-10-01'<=r['announcement_date']<='2026-11-19'for r in rows):raise ValueError('endpoint reasons directory scope changed')
 for r in rows:
  raw=r['raw_item'];day=datetime.fromtimestamp(raw['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(raw['announcementId'])!=r['announcement_id']or raw['secCode']!='002717'or day!=r['announcement_date']or r['url']!='https://static.cninfo.com.cn/'+raw['adjunctUrl']:raise ValueError('endpoint reasons directory identity changed')
 matched=[r for r in rows if ('终止上市'in r['title']or'摘牌'in r['title'])and not any(t in r['title']for t in ['事先','风险提示','将被'])]
 prices={(r['symbol'],r['trade_date']):r for r in m['fixed_prices']};wins=[]
 for key,comparison,days in [('full',current['full_comparison']['fixed_after'],93),('recent',current['fixed'],9)]:
  fixed=comparison['rows'];covered=sum(r['return_pct']is not None for r in fixed)
  if len(fixed)!=150 or covered!=comparison['covered']or 150-covered!=comparison['missing']:raise ValueError('endpoint reasons denominator changed')
  out=[]
  for code in CODES:
   r=next(r for r in fixed if r['symbol']==code);a,z=comparison['anchor'],comparison['through'];states=[]
   for side,day in [('anchor',a),('endpoint',z)]:
    status=r['endpoint_trade_states'][side]['status'];quote=prices.get((code,day));actual=status=='traded'
    if actual and(not quote or not quote['has_trade']or quote['raw_volume']<=0):raise ValueError('endpoint reasons traded endpoint lacks evidence')
    if not actual and quote and quote['has_trade']:raise ValueError('endpoint reasons nontrade conflicts')
    if actual:meaning='当日有成交'
    elif code=='000016'and day>='2026-10-23':meaning='已主动摘牌，无该所当日成交价'
    elif code=='002717'and day>='2026-10-13':meaning='停牌；最终决定和摘牌日未核'
    elif code=='002731'and day>='2026-11-13':meaning='已摘牌，无该所当日成交价'
    elif code=='002731'and day=='2026-07-03':meaning='年报披露事项停牌，7月7日才复牌'
    elif code=='600491'and day=='2026-07-03':meaning='筹划事项停牌，7月10日才复牌'
    else:raise ValueError('endpoint reasons unexplained missing endpoint')
    states.append({'date':day,'data_status':status,'traded_qfq_close':quote['close']if actual else None,'reference_qfq_close':quote['close']if quote else None,'meaning':meaning})
   out.append({'symbol':code,'name':r['name'],'return_pct':r['return_pct'],'gap':r['gap'],'anchor':states[0],'endpoint':states[1],'provider_st_at_end':r['still_st_at_end']})
  wins.append({'key':key,'anchor':comparison['anchor'],'through':comparison['through'],'days':days,'total':150,'covered':covered,'missing':150-covered,'rows':out})
 if [w['missing']for w in wins]!=[4,3]:raise ValueError('endpoint reasons expected missing sets changed')
 # Confirm the continuing halt through the new nine sessions without treating missing prices as zero returns.
 acts={(r['symbol'],r['trade_date']):r for r in m['activities']};newdays=[d for d in m['calendar']if '2026-11-06'<d<='2026-11-19']
 if len(newdays)!=9 or any((r:=acts.get(('002717',d)))is None or r['suspension_status']!='suspended'or(r.get('volume')or 0)>0 for d in newdays):raise ValueError('endpoint reasons Lingnan halt not corroborated')
 public=lambda s:{k:v for k,v in s.items()if k not in ['selected_pages','page_hashes']}
 specs=[('000016','主动摘牌，有现金选择权申报交收','9月4日停牌，10月23日主动摘牌。公告称有效申报现金选择权完成交收，但资格、实际申报、成本及到账不能据此推算每个持有人收益。',[('1225545707',[1]),('1225605494',[2]),('1225615607',[1])]),('002717','交易类触发停牌，已核至事先告知','10月13日停牌，10月17日披露16日收到拟终止上市事先告知。原件保留听证和申辩；最终决定及摘牌未核，不把程序期限或目录没检出当作完成或不存在。',[('1225602315',[1,2]),('1225609701',[1,2])]),('002731','起点停牌，期末已摘牌','7月3日仍因年报事项停牌，7月7日复牌；10月23日起退市整理，11月12日最后交易，11月13日摘牌。最近9日有11月6日起点，完整93日却没有7月3日成交起点。',[('1225607488',[2]),('1225669888',[1,2])]),('600491','筹划事项停牌后复牌，不是退出样本','7月3日至9日筹划事项停牌，7月10日复牌。完整93日缺的是起点实际成交；11月6日至19日已有共同成交端点。复牌本身不证明要约完成、控制权改变或风险解除。',[('1225407586',[1]),('1225417943',[1])])]
 cases=[{'symbol':code,'title':title,'reading':reading,'sources':[{'source':public(sources[aid]),'pages':ns}for aid,ns in refs]}for code,title,reading,refs in specs]
 return {'through':current['through'],'windows':wins,'cases':cases,'directory_review':{'symbol':'002717','start':'2026-10-01','through':'2026-11-19','record_count':34,'matched_final_titles':[r['title']for r in matched],'query_url':cat['refs'][0]['url'],'scope':'仅检查本次完整返回目录标题；标题未检出不证明不存在目录外或标题未显露的最终文件。'},'counts':{'new_primary_documents':0,'reused_primary_documents':9,'reused_primary_pages':sum(s['pages']for s in sources.values()),'rechecked_rendered_pages':10,'new_price_points':0},'boundaries':['150只历史样本全部保留；146或147只是各窗口可计算子集，缺口不填零，也不拿别日价格补成当日期末成交。','实际成交状态、提供方ST成员身份与公司法律程序是三个维度；停牌可以仍在提供方名单，离开名单也不等于摘帽成功。','康佳现金选择权交收不是11月19日交易价；萃华最后交易价也不是摘牌后可成交价。','目录检查是补核范围，不是交易所最终决定；岭南最终节点仍需原件。','复用原件和重复核对不增加独立案例或经验验证次数；本轮没有新增行情或完整官方名单认证。'],'method_promotions':0}
