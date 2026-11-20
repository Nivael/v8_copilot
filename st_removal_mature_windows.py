"""Mature follow-up windows remain unverified when endpoint prices conflict."""
from decimal import Decimal as D
from statistics import median
from hashlib import sha256
from copy import deepcopy
import json
from canonical_json import digest

def calculate_mature_windows(inputs,prior):
    m=inputs['current_extension']['market_inputs'];dates=sorted(m['calendar']);assert len(dates)==len(set(dates));prices={(r['symbol'],r['trade_date']):r for r in m['fixed_prices']};index={r['trade_date']:D(str(r['close']))for r in m['benchmarks']if r['benchmark_id']=='csi_all_share'};cross={};sources=[]
    for s in inputs['endpoint_selection_audit']['sources']:
     assert sha256(s['text'].encode()).hexdigest()==s['sha256'];b=json.loads(s['text'])['data'][s['provider_key']];cross[s['symbol']]={r[0]:r for r in b.get('qfqday',b.get('day',[]))};sources.append({'symbol':s['symbol'],'sha256':s['sha256'],'url':s['url']})
    ix=next(s for s in inputs['initial_twentyseventh_four']['cross_sources']if s['key']=='000985');assert sha256(ix['text'].encode()).hexdigest()==ix['sha256'];official={r['tradeDate']:D(str(r['close']))for r in json.loads(ix['text'])['data']}
    rows=[]
    for event in prior['rows']:
     if event['era']!='post':continue
     code=event['symbol'];anchor=event['resume_close_on'];after=[d for d in dates if anchor<d<='2026-11-19'];end=after[19]if len(after)>=20 else None;checks=[]
     if end:
      for d in [anchor,end]:
       a=prices.get((code,d));b=cross[code].get(d);at=bool(a and a['has_trade']and D(str(a['raw_volume']))>0);bt=bool(b and D(str(b[5]))>0);difference=D(str(a['close']))-D(str(b[2]))if at and bt else None
       checks.append({'date':d,'primary_close':str(a['close'])if at else None,'cross_close':str(b[2])if bt else None,'difference':str(difference)if difference is not None else None,'status':'matched'if difference is not None and abs(difference)<D('1e-9')else'price_conflict'if difference is not None else'missing'})
      for d in [anchor,end]:assert abs(index[d]-official[d.replace('-','')])<D('.005')
     def ret(key):return str((D(checks[1][key])/D(checks[0][key])-1)*100)if len(checks)==2 and all(x[key]is not None for x in checks)else None
     primary=ret('primary_close');other=ret('cross_close');valid=bool(end and all(x['status']=='matched'for x in checks));market=str((index[end]/index[anchor]-1)*100)if end else None;old=event['windows']['20']['from_resume_close']
     if old['status']=='valid':assert valid and abs(D(primary)-D(str(old['stock_pct'])))<D('1e-10')and end==old['through']
     rows.append({'symbol':code,'name':event['name'],'anchor':anchor,'through':end,'available_market_days':len(after),'status':'matched'if valid else'price_conflict'if end else'insufficient_followup','certified_stock_pct':primary if valid else None,'primary_stock_pct':primary,'cross_stock_pct':other,'market_pct':market,'endpoints':checks,'prior_status':old['status'],'prior_through':old['through'],'newly_mature':old['status']=='insufficient_followup'and end is not None})
    values=[D(r['certified_stock_pct'])for r in rows if r['certified_stock_pct']is not None];prior=[D(str(e['windows']['20']['from_resume_close']['stock_pct']))for e in prior['rows']if e['era']=='post'and e['windows']['20']['from_resume_close']['status']=='valid'];assert len(rows)==12 and len(prior)==10
    result={'source_snapshot':SOURCE_SNAPSHOT,'through':'2026-11-19','event_group':'此前已核12次制度后撤销事件，非新增完整事件全集','horizon':'摘帽首日收盘之后20个市场交易日；不含首日跳变','rows':rows,'summary':{'events':12,'mature':sum(r['through']is not None for r in rows),'direct_verified':len(values),'price_conflicts':sum(r['status']=='price_conflict'for r in rows),'positive':sum(x>0 for x in values),'negative':sum(x<0 for x in values),'median_pct':str(median(values)),'prior_direct_verified':len(prior),'prior_positive':sum(x>0 for x in prior),'prior_median_pct':str(median(prior))},'source_refs':[s for s in sources if s['symbol']in {r['symbol']for r in rows}],'boundary':'后窗成熟不等核价通过；绝味起点报价差异未消除，精确核验收益留空。11家中位数不能当全12家，不与制度前37次作因果胜负比较；不同事件日期的大盘环境不同。原截至11月6日版本保留。'}
    return result

def removal_mature_windows(inputs,prior):
    packet=inputs.get("removal_mature_windows")
    if packet is None:return None
    if packet.get("version")!=1 or packet.get("content_digest")!=digest({k:v for k,v in packet.items()if k!="content_digest"}):raise ValueError("mature window packet changed")
    scope={"market":inputs["current_extension"]["market_inputs"],"cross":inputs["endpoint_selection_audit"]["sources"],"official":inputs["initial_twentyseventh_four"]["cross_sources"],"prior":prior}
    if digest(scope)!=SCOPE_DIGEST:raise ValueError("mature window sources changed")
    calculated=calculate_mature_windows(inputs,prior)
    if calculated!=packet["result"]or digest(calculated)!=RESULT_DIGEST:raise ValueError("mature window result changed")
    return deepcopy(calculated)

SOURCE_SNAPSHOT='c2c15689368d763b2a5ef415086457af160a35ffd39cc9f0421971f9e347e733'
SCOPE_DIGEST='075d904a3437ae22bf56ee29e1a58ff3771067e6ea500ba0b9cd8a3c1358b6cf'
RESULT_DIGEST='0720ea2686482bd465a85137fccb92055fbe2a2a93a9cbe4de4ca1947e3423a7'
