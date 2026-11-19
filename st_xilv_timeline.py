"""Read-only Xilv timeline: dated issuer facts and shared, non-causal price windows."""
from decimal import Decimal as D, ROUND_HALF_UP
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re,unicodedata
from canonical_json import digest

GROUPS=[
 ('forecast','2026-07-15',['1225424856'],'仍预计亏损','上半年归母净利润预亏4000万—6000万元，未经审计；不能用后续上涨反证当时预亏失真。'),
 ('pre','2026-09-01',['1225538581','1225538017','1225538584'],'原定增终止，转向预重整','收到8月31日启动预重整及指定临时管理人的决定，另终止原定增并招募投资人。预重整尚非正式受理重整；同日三份文件是相关事项。'),
 ('agreement','2026-09-22',['1225575791'],'投资人已签约，实施仍有条件','9月18日签约，22日披露。5000万元是监督方指定账户的报名保证金，转为履约保证金；投资款支付、法院批准和股份登记仍分别有条件。'),
 ('quarter','2026-10-24',['1225621541'],'财务风险仍在','未经审计三季报列前三季归母净利润约负7917万元、9月末归母净资产约负1.337亿元；年末比较数约负5454万元。'),
 ('loan','2026-10-31',['1225650665'],'收到首期经营借款','10月30日签约并收到首期1000万元。总额度不超过2800万元、年息4%，后续另行确认；借款有偿还义务，不能当捐赠或等额净资产修复。'),
 ('abnormal','2026-11-04',['1225656284'],'异动公告回看已发生的上涨','公告核对10月30日、11月2日、3日的上涨偏离；不能把11月4日当成前三天上涨之前的新经营催化。'),
 ('amendment','2026-11-05',['1225658226'],'补充协议有增加，也有删除','延长有关股份锁定至60个月、增加自有资金超过50%的承诺，同时删去牵头人或指定第三方对联合体其他成员投资义务的连带责任。公告仍称未收到正式受理重整的法律文书，仅认证到该披露时点。'),
]
CLAUSES={
 ('1225424856',1):['-6,000','-4,000','未经过注册会计师预审计'],
 ('1225538581',1):['2026年8月31日','不代表法院正式受理'],
 ('1225538017',2):['终止本次向特定对象发行股票事项'],
 ('1225538584',1):['不代表法院正式受理','招募'],
 ('1225575791',3):['2026年9月18日','三元好时光'],
 ('1225575791',19):['5,000.00万元','指定账户'],
 ('1225575791',20):['五个工作日','全部投资款','先决条件'],
 ('1225621541',1):['□是否'],
 ('1225621541',2):['-133,706,602.68','-79,170,708.25','-54,535,894.43'],
 ('1225650665',2):['首期借款1,000万元','2026年10月30日'],
 ('1225650665',3):['28,000,000.00','年利率为4%','偿还'],
 ('1225656284',1):['2026年10月30日','2026年11月2日','2026年11月3日'],
 ('1225658226',4):['60个月','超过50%','连带责任','删除条款'],
 ('1225658226',5):['尚未收到法院关于受理重整申请'],
}
PHASES=[
 ('7月：先跌','亏损预期仍在，西旅与ST、大盘同跌。完整93日的上涨，不能抹去最初20日的回撤。'),
 ('8月：共同修复','西旅、ST、大盘与小盘都回升。西旅8月11日已重新超过7月3日收盘，早于9月预重整披露。'),
 ('9月：与市场背离','预重整、投资人及协议使化债路径更具体，但月内先冲高后回落；不能把整月上涨都归给月底前的一份协议。'),
 ('10月：共同回撤','西旅和ST、大盘共同下跌。三季报仍亏损且净资产为负，签约进展与财务修复不能混成一件事。'),
 ('11月截至19日：再次背离','西旅反弹而三个参考下跌；经营借款首期实收和协议条款变化须分别跟踪，不能由价格倒推出重整完成。'),
]

def printed_date(source):
 from st_initial_warning_origin import origin_document_date
 # Recruitment's signed main notice ends on page 11; later pages are blank-date forms.
 page=11 if source['announcement_id']=='1225538584'else source['pages']
 return origin_document_date({**source,'pages':page})

def xilv_timeline(inputs,current):
 p=inputs.get('xilv_timeline')
 if p is None:return None
 if p.get('version')!=1 or p.get('content_digest')!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('xilv packet changed')
 m=inputs['current_extension']['market_inputs']
 if not current or current['through']!='2026-11-19'or p['current_digest']!=digest(current)or p['market_digest']!=digest(m):raise ValueError('xilv market binding changed')
 sources={s['announcement_id']:s for s in p['sources']};expected={aid:day for _,day,ids,_,_ in GROUPS for aid in ids}
 if len(p['sources'])!=9 or set(sources)!=set(expected):raise ValueError('xilv source set changed')
 for aid,s in sources.items():
  meta=s['raw_item'];pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  if str(meta['announcementId'])!=aid or meta['secCode']!='000610'or s['symbol']!='000610'or s['title']!=meta['announcementTitle']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub!=expected[aid]or not s['protected_gate_passed']:raise ValueError('xilv primary identity/date changed')
  if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('xilv pages incomplete')
  for n,t in s['selected_pages'].items():
   if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('xilv page changed')
  if printed_date(s)!=s['document_dated_on']:raise ValueError('xilv printed date changed')
 for (aid,n),tokens in CLAUSES.items():
  if any(token not in sources[aid]['selected_pages'][str(n)]for token in tokens):raise ValueError('xilv stage/amount clause changed')
 catalog=p['catalog'];rows=catalog['rows']
 if catalog['total']!=32 or len(rows)!=32 or len({r['announcement_id']for r in rows})!=32 or any(r['symbol']!='000610'or not '2026-07-01'<=r['announcement_date']<='2026-11-19'for r in rows):raise ValueError('xilv catalog scope changed')
 byid={r['announcement_id']:r for r in rows}
 if any(s['raw_item']!=byid[aid]['raw_item']for aid,s in sources.items()):raise ValueError('xilv catalog binding changed')
 dates=sorted(d for d in m['calendar']if '2026-07-03'<=d<='2026-11-19')
 prices={r['trade_date']:r for r in m['fixed_prices']if r['symbol']=='000610'and '2026-07-03'<=r['trade_date']<='2026-11-19'}
 if len(dates)!=94 or len(set(dates))!=94 or set(prices)!=set(dates)or any(not r['has_trade']or r['raw_volume']<=0 for r in prices.values()):raise ValueError('xilv daily price coverage changed')
 bench={(r['benchmark_id'],r['trade_date']):D(str(r['close']))for r in m['benchmarks']}
 from st_regime_comparison import build
 st={r['date']:D(str(r['return_pct']))for r in build(m)['daily']}
 cross={s['key']:s for s in p['cross_sources']}
 if set(cross)!={'sz000610','000985','932000'}or len(p['cross_sources'])!=3:raise ValueError('xilv crossquote scope changed')
 for key,s in cross.items():
  url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000610,day,2026-07-03,2026-11-19,320,qfq'if key=='sz000610'else f'https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={key}&startDate=20260703&endDate=20261119'
  if s['url']!=url or sha256(s['text'].encode()).hexdigest()!=s['sha256']:raise ValueError('xilv crossquote identity changed')
 q={r[0]:r for r in json.loads(cross['sz000610']['text'])['data']['sz000610']['qfqday']};diff=[];tail=D(0)
 for d in dates:
  delta=abs(D(q[d][2])-D(str(prices[d]['close'])));tail=max(tail,delta)
  if delta>D('1e-9')or D(q[d][5])<=0:raise ValueError('xilv stock daily crossquote mismatch')
 for code,label in [('000985','csi_all_share'),('932000','csi_2000')]:
  official={r['tradeDate']:r for r in json.loads(cross[code]['text'])['data']}
  for d in dates:
   r=official[d.replace('-','')];a=bench[(label,d)];z=D(str(r['close']))
   if r['indexCode']!=code or a.quantize(D('.01'),rounding=ROUND_HALF_UP)!=z:raise ValueError('xilv index daily crossquote mismatch')
   if a!=z:diff.append({'index':code,'date':d,'provider':str(a),'official':str(z)})
 def window(a,z):
  days=[d for d in dates if a<d<=z];s=D(1)
  for d in days:s*=1+st[d]/100
  return {'anchor':a,'through':z,'days':len(days),'stock_pct':float((D(str(prices[z]['close']))/D(str(prices[a]['close']))-1)*100),'st_pct':float((s-1)*100),'market_pct':float((bench[('csi_all_share',z)]/bench[('csi_all_share',a)]-1)*100),'small_pct':float((bench[('csi_2000',z)]/bench[('csi_2000',a)]-1)*100)}
 ends=['2026-07-03','2026-07-31','2026-08-31','2026-09-30','2026-10-30','2026-11-19']
 monthly=[{**window(a,z),'title':title,'reading':reading}for (a,z),(title,reading)in zip(zip(ends,ends[1:]),PHASES)]
 public=lambda s:{k:v for k,v in s.items()if k not in ('selected_pages','page_hashes','raw_item')}
 events=[]
 for key,pub,ids,title,reading in GROUPS:
  a=max(d for d in dates if d<pub);future=[d for d in dates if d>=pub];ws=[]
  for n in [1,5,20]:
   w=window(a,future[n-1])if len(future)>=n else {'anchor':a,'through':None,'days':None,'stock_pct':None,'st_pct':None,'market_pct':None,'small_pct':None}
   ws.append({**w,'requested_days':n,'available_days':len(future),'complete':len(future)>=n})
  events.append({'key':key,'published_on':pub,'title':title,'reading':reading,'sources':[{**public(sources[aid]),'pages_to_read':sorted(n for (a,n)in CLAUSES if a==aid)}for aid in ids],'windows':ws})
 path=[{'date':d,'stock_close':prices[d]['close'],**{k:v for k,v in window(dates[0],d).items()if k.endswith('_pct')}}for d in dates]
 return {'version':1,'symbol':'000610','anchor':dates[0],'through':dates[-1],'monthly':monthly,'events':events,'path':path,'full':window(dates[0],dates[-1]),'hindsight_extrema':{'lowest_close':min(path,key=lambda r:r['stock_close']),'highest_close':max(path,key=lambda r:r['stock_close'])},'first_recovery_after_july':next(r for r in path if r['date']>'2026-07-31'and r['stock_close']>=path[0]['stock_close']),'crosscheck':{'stock_daily_points':94,'official_index_daily_points':188,'stock_max_float_tail':str(tail),'unrounded_index_differences':diff,'sources':[{k:v for k,v in s.items()if k!='text'}for s in p['cross_sources']]},'counts':{'catalog_rows':32,'pdf_files':9,'pdf_pages':sum(s['pages']for s in sources.values()),'event_groups':7,'complete_windows':sum(w['complete']for e in events for w in e['windows']),'incomplete_windows':sum(not w['complete']for e in events for w in e['windows'])},'boundaries':['披露日窗口以前一交易日收盘为锚；准确发布时间未核，不能当看到公告后可执行的收益。','同日文件归同一事项组，窗口可重叠，不作多次独立验证。','原件认证状态只到各自披露日；11月5日尚未收到受理文书，不等于11月19日全面查明的法院状态。','9份是32条目录中的有目的选样，诉讼、担保与其他股东借款等未全部读正文。','跨渠道一致不证明底层供应链完全独立；同涨同跌与相对收益都不能分离公告净贡献。'],'method_promotions':0,'tracked_list_changed':False}
