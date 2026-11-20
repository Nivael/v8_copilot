"""Nonoverlapping date intervals do not establish independent regime experiments."""
from pathlib import Path
from decimal import Decimal as D,ROUND_HALF_UP
from statistics import median
from hashlib import sha256
from copy import deepcopy
import json
from canonical_json import digest

def market_stage_experience(inputs,priors):
    packet=inputs.get('market_stage_experience')
    if packet is None:return None
    if packet.get('version')!=1 or packet.get('content_digest')!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('market stages packet changed')
    if digest(priors)!=PRIOR_DIGEST:raise ValueError('market stages prior changed')
    i=inputs;v={'themes':priors}
    scope={'market':i['current_extension']['market_inputs'],'quotes':i['endpoint_selection_audit']['sources'],'official':next(s for s in i['initial_twentyseventh_four']['cross_sources']if s['key']=='000985')}
    if digest(scope)!=SCOPE_DIGEST:raise ValueError('market stages source scope changed')
    from st_regime_comparison import build
    m=i['current_extension']['market_inputs'];daily=build(m)['daily'];prices={(r['symbol'],r['trade_date']):r for r in m['fixed_prices']};refs=i['endpoint_selection_audit']['sources'];cross={}
    for s in refs:
     assert sha256(s['text'].encode()).hexdigest()==s['sha256'];body=json.loads(s['text'])['data'].get(s['provider_key'],{});cross[s['symbol']]={r[0]:r for r in body.get('qfqday',body.get('day',[]))}
    codes=[r['symbol']for r in v['themes']['endpoint_selection_audit']['windows'][0]['rows']];assert len(set(codes))==150
    index_source=next(s for s in i['initial_twentyseventh_four']['cross_sources']if s['key']=='000985');assert sha256(index_source['text'].encode()).hexdigest()==index_source['sha256'];official={r['tradeDate']:D(str(r['close']))for r in json.loads(index_source['text'])['data']};index={r['trade_date']:D(str(r['close']))for r in m['benchmarks']if r['benchmark_id']=='csi_all_share'}
    bounds=['2026-07-03','2026-07-31','2026-08-31','2026-09-30','2026-10-30','2026-11-19'];stages=[]
    for a,z in zip(bounds,bounds[1:]):
     ds=[r for r in daily if a<r['date']<=z];stock_rows=[]
     for code in codes:
      endpoints=[]
      for d in [a,z]:
       primary=prices.get((code,d));other=cross[code].get(d);pt=bool(primary and primary['has_trade'] and D(str(primary['raw_volume']))>0);ct=bool(other and D(str(other[5]))>0);delta=D(str(primary['close']))-D(str(other[2]))if pt and ct else None;status='matched'if delta is not None and abs(delta)<D('1e-9')else'price_conflict'if pt and ct else'cross_missing'if pt else'primary_missing'
       endpoints.append({'date':d,'status':status,'primary_close':str(primary['close'])if pt else None,'cross_close':str(other[2])if ct else None,'difference':str(delta)if delta is not None else None})
      pr=(D(endpoints[1]['primary_close'])/D(endpoints[0]['primary_close'])-1)*100 if all(r['primary_close']is not None for r in endpoints)else None
      good=all(r['status']=='matched'for r in endpoints)
      stock_rows.append({'symbol':code,'status':'matched'if good else'unverified'if pr is not None else'primary_gap','return_pct':str(pr)if pr is not None else None,'certified_return_pct':str(pr)if good else None,'endpoints':endpoints})
     def compound(rows,key):
      value=D(1)
      for r in rows:value*=1+D(str(r[key]))/100
      return (value-1)*100
     st=compound(ds,'return_pct');market=(index[z]/index[a]-1)*100
     for d in [a,z]:assert index[d].quantize(D('.01'),rounding=ROUND_HALF_UP)==official[d.replace('-','')]
     vals=[D(r['certified_return_pct'])for r in stock_rows if r['certified_return_pct']is not None];primary=[D(r['return_pct'])for r in stock_rows if r['return_pct']is not None]
     stages.append({'anchor':a,'through':z,'market_days':len(ds),'st_pct':str(st),'market_pct':str(market),'st_minus_market_pp':str(st-market),'fixed_members':150,'primary_paired':len(primary),'verified_paired':len(vals),'primary_gaps':150-len(primary),'unverified_paired':len(primary)-len(vals),'verified_median_pct':str(median(vals)),'verified_positive':sum(r>0 for r in vals),'primary_median_pct':str(median(primary)),'rows':stock_rows,'daily_dates':[r['date']for r in ds]})
    common=set.intersection(*[{r['symbol']for r in stage['rows']if r['status']=='matched'}for stage in stages])
    for stage in stages:
     common_values=[D(r['certified_return_pct'])for r in stage['rows']if r['symbol']in common]
     stage['common_sample']={'members':len(common),'symbols':sorted(common),'median_pct':str(median(common_values)),'positive':sum(x>0 for x in common_values)}
    all_dates=[d for s in stages for d in s['daily_dates']];assert len(all_dates)==len(set(all_dates))==93
    result={'through':'2026-11-19','stages':stages,'new_quote_requests':0,'reused_stock_responses':len(refs),'nonoverlapping_market_days':93,'common_verified_members':len(common),'unique_stock_endpoint_checks':len(codes)*len(bounds),'unique_official_index_dates':len(bounds),'independent_regime_experiments':0,'method_promotions':0,'boundary':'五段按月末及已核截止划分，收益日不重叠，但同一时期同一股票池不构成五次独立制度试验；各段核价通过子样本分母不同，动态ST复合不是固定样本中位数或可交易组合。7月从3日收盘起、11月只到19日，都不是整月。'}
    expected=packet['result']
    if digest(expected)!=VIEW_DIGEST or any(expected[k]!=value for k,value in result.items()):raise ValueError('market stages result changed')
    return deepcopy(expected)

PRIOR_DIGEST='9766eaa2b9c90685d3273442f6328514487e4ba706c301137a4bba59c64cde1c'
SCOPE_DIGEST='707b7e3368ac82bd6e7750e690d478816b5c1daaca5303c0661c6237e8f0d648'
VIEW_DIGEST='f802260736651b5ab5d67c5b9b3c6bcd23295edd6445cf31036cdedec55f16d7'
