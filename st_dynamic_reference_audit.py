"""A source-bound parallel quote line, conditional on the existing historical member list."""
from decimal import Decimal as D
from statistics import mean,pstdev
from math import prod
from canonical_json import digest
from st_stock_price_crosscheck import quotes_from_source
PREFIXES=('000','001','002','003','600','601','603','605')
KEYS=('calendar','through','members','activities','benchmarks','member_entries')
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def cumulative(rows):return (prod(1+r['return_pct']/100 for r in rows)-1)*100
def relation(rows):
 x=[r['market_pct']for r in rows];y=[r['return_pct']for r in rows];a,b=mean(x),mean(y);cov=mean((u-a)*(v-b)for u,v in zip(x,y,strict=True));return cov/(pstdev(x)*pstdev(y))if pstdev(x)and pstdev(y)else None

def dynamic_reference_audit(i,daily):
 p=i.get('dynamic_reference_audit')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'})or p['scope_digest']!=scope_digest(i)or p['through']!=i['through']:raise ValueError('dynamic audit binding changed')
 names={r['symbol']:r['name']for r in i['members']if r['symbol'].startswith(PREFIXES)};members={(r['symbol'],r['trade_date'])for r in i['members']if r['symbol']in names};activities={(r['symbol'],r['trade_date']):r for r in i['activities']};original=p['original_prices'];companies=original['companies']
 if len(names)!=203 or len(companies)!=203 or {c['symbol']for c in companies}!=set(names)or original['calendar']!=i['calendar']or original['through']!=i['through']:raise ValueError('dynamic membership scope changed')
 base={}
 for c in companies:
  if [r['date']for r in c['rows']]!=i['calendar']:raise ValueError('dynamic price calendar changed')
  for r in c['rows']:
   if r['has_trade']!=bool(r['volume']is not None and r['volume']>0):raise ValueError('dynamic cached trade state changed')
   base[(c['symbol'],r['date'])]=r
 maps={};sources=p['sources']
 if len(sources)!=406:raise ValueError('dynamic quote set incomplete')
 for s in sources:
  pair=(s['symbol'],s['key'])
  if pair in maps or pair[0]not in names or pair[1]not in ('tencent_raw','tencent_qfq')or not s.get('url')or not s.get('observed_at')or type(s['reused'])is not bool:raise ValueError('dynamic source identity or metadata changed')
  q=quotes_from_source(s)
  if not set(q)<=set(i['calendar']):raise ValueError('dynamic quote outside window')
  maps[pair]=q
 reference=p['resume_reference'];s=reference['source'];qref=quotes_from_source(s)
 if s['symbol']!='002731'or s['key']!='eastmoney_raw'or reference['date']!='2026-07-07'or reference['symbol']!='002731':raise ValueError('resume source identity changed')
 import json
 b=json.loads(s['raw_text'])['data'];bars=[x.split(',')for x in b['klines']];row=next(x for x in bars if x[0]==reference['date']);resume_pre=D(row[2])-D(row[9])
 if resume_pre<=0 or resume_pre!=D(reference['reference'])or D(row[2])!=qref[reference['date']]:raise ValueError('resume reference arithmetic changed')
 out=[];differences=[];fallbacks=[];observations=0;suspensions=0;raw_checked=set();empty=[]
 for sym in sorted(names):
  if set(maps[(sym,'tencent_raw')])!=set(maps[(sym,'tencent_qfq')]):raise ValueError('raw/qfq quote dates disagree')
  if not maps[(sym,'tencent_raw')]:
   a=[activities[(sym,d)]for s,d in members if s==sym]
   if not a or any(x['suspension_status']!='suspended'for x in a):raise ValueError('unexplained empty quote series')
   empty.append({'symbol':sym,'name':names[sym],'member_days':len(a),'all_member_days_suspended':True})
 for primary in daily:
  day=primary['date'];observed=[];suspended=[];rates=[]
  for sym in sorted(s for s,d in members if d==day):
   a=activities[(sym,day)];b=base[(sym,day)];raw=maps[(sym,'tencent_raw')];q=maps[(sym,'tencent_qfq')]
   if a['suspension_status']=='suspended':
    if day in raw or b['has_trade']:raise ValueError('public trade during classified suspension')
    suspended.append(sym);continue
   if a['suspension_status']!='trading'or a['terminal_phase_status']!='not_terminal'or not b['has_trade']or day not in raw or day not in q or raw[day]!=D(str(a['close']))or raw[day]!=D(str(b['raw_close']))or D(str(a['pre_close']))!=D(str(b['pre_close'])):raise ValueError('dynamic actual quote/cache conflict')
   prev=max((d for d in q if d<day),default=None);observed.append(sym);raw_checked.add((sym,day));observations+=1
   if prev is None:
    if(sym,day)!=(reference['symbol'],reference['date'])or raw[day]!=D(row[2])or resume_pre!=D(str(a['pre_close'])):raise ValueError('missing independent previous price/reference')
    rate=float((D(row[2])/resume_pre-1)*100);fallbacks.append({'symbol':sym,'date':day,'reference':str(resume_pre),'close':str(raw[day]),'mode':'eastmoney_close_minus_change','previous_actual_date_verified':False,'source':{k:s[k]for k in ('url','sha256','observed_at')}})
   else:rate=float((q[day]/q[prev]-1)*100)
   rates.append(rate)
   if abs(rate-a['pct_chg'])>.0001:differences.append({'symbol':sym,'name':names[sym],'date':day,'primary_pct':a['pct_chg'],'parallel_pct':rate,'difference_pp':rate-a['pct_chg'],'previous_actual':prev,'reference':a['pre_close'],'previous_raw':float(raw[prev])if prev else None})
  if len(observed)!=primary['observed_count']or suspended!=primary['suspended']or primary['member_count']!=len(observed)+len(suspended)or not rates:raise ValueError('dynamic contributors differ')
  suspensions+=len(suspended);value=mean(rates);out.append({'date':day,'member_count':primary['member_count'],'observed_count':len(observed),'suspended_count':len(suspended),'contributor_digest':digest(observed),'primary_pct':primary['return_pct'],'return_pct':value,'difference_pp':value-primary['return_pct'],'market_pct':primary['market_pct'],'daily_sign_changed':(value>0)!=(primary['return_pct']>0)})
 windows=[];before=[r for r in out if r['date']<'2026-07-06'];after=[r for r in out if r['date']>='2026-07-06']
 for key,n in [('20',20),('40',40),('all',None)]:
  for side,rows in [('before',before[-(n or 40):]),('after',after[:n]if n else after)]:
   old=[{'return_pct':r['primary_pct'],'market_pct':r['market_pct']}for r in rows];conditions=[]
   for label,test in [('up',lambda x:x>0),('down',lambda x:x<0),('stress',lambda x:x<-1)]:
    selected=[r for r in rows if test(r['market_pct'])];conditions.append({'key':label,'days':len(selected),'primary_mean_pct':mean(r['primary_pct']for r in selected)if selected else None,'parallel_mean_pct':mean(r['return_pct']for r in selected)if selected else None})
   a,b=cumulative(old),cumulative(rows);windows.append({'key':key,'side':side,'start':rows[0]['date'],'through':rows[-1]['date'],'days':len(rows),'primary_change_pct':a,'parallel_change_pct':b,'difference_pp':b-a,'market_pct':(prod(1+r['market_pct']/100 for r in rows)-1)*100,'primary_correlation':relation(old),'parallel_correlation':relation(rows),'conditions':conditions,'direction_changed':(a>0)!=(b>0)})
 entrants=[]
 for e in i['member_entries']['rows']:
  sym=e['symbol'];all_days=[r['date']for r in out if(sym,r['date'])in members];days=[d for d in all_days if d>=e['effective_on']];prior_days=[d for d in all_days if d<e['effective_on']];active=[d for d in days if(sym,d)in raw_checked];entrants.append({'symbol':sym,'name':e['new_name'],'effective_on':e['effective_on'],'first_member':min(days),'member_days':len(days),'prior_member_days':len(prior_days),'prior_last_member':max(prior_days)if prior_days else None,'actual_traded_member_days':len(active),'suspended_member_days':len(days)-len(active),'member_price_match':True})
 fixed={r['symbol']for r in i['members']if r['trade_date']=='2026-07-03'and r['symbol']in names};prior_only=sorted(set(names)-fixed-{e['symbol']for e in i['member_entries']['rows']});points=sum(len(q)for q in maps.values())
 return {'through':i['through'],'answer':('按既有逐日名单，203家公司在125日内的实际成交贡献与独立收盘对齐；平行报价线的每日涨跌方向、制度前后窗口涨跌方向均未改变。'if not any(r['daily_sign_changed']for r in out)and not any(w['direction_changed']for w in windows)else'平行核验出现涨跌方向差异，须逐日与逐窗口核对，不能沿用方向一致的判断。')+'价格核对不替代历史名单独立认证，复权构造差异也不覆盖原线。','companies':203,'pre_rule_only_companies':len(prior_only),'pre_rule_only_symbols':prior_only,'daily':out,'days':len(out),'trading_observations':observations,'suspended_observations':suspensions,'valid_responses':len(sources),'new_responses':sum(not s['reused']for s in sources),'reused_responses':sum(s['reused']for s in sources),'quote_points':points,'provider_cache_responses':len(original['source_refs']),'empty_series':empty,'resume_references':fallbacks,'entrants':entrants,'windows':windows,'daily_sign_changes':sum(r['daily_sign_changed']for r in out),'max_daily_difference_pp':max(abs(r['difference_pp'])for r in out),'stock_rate_difference_observations':len(differences),'stock_rate_differences':sorted(differences,key=lambda r:abs(r['difference_pp']),reverse=True),'sources':[{k:s[k]for k in ('symbol','key','url','sha256','observed_at','reused')}for s in sources],'lookback_failures':p['lookback_failures'],'boundary':'只按既有历史名单核价格贡献，未把203家历史全名单逐日独立认证。腾讯两复权口径为一渠道；平行线多数用相邻实际成交的直接前复权比值，萃华复牌日独立参考额另列，价格构造与原线日参考价口径不同。已冻结来源不能还原历史当时的报价界面，也不能证明规则或公告净因果。'}
