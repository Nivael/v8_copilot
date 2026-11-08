"""Authorized, resumable provider materialization for the ST regime study.

Credentials are read only from a private env file; request bodies are never
persisted. Successful original response bytes, public query parameters, and
scoped normalized inputs are kept outside research SQLite databases.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,datetime,timezone
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import threading
import time
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import sessions_2026
from provider_env import load_provider_env
from settings import DATA_ROOT
from st_regime_comparison import ROOT,VERSION,ANCHOR,main_board
import os

ACQUISITION_VERSION='st_regime_provider_acquisition_v1'
CACHE=DATA_ROOT/'local_data/v8_copilot/market_risk/st_regime_acquisition/20261109'
FIELDS={
 'stock_st':'ts_code,name,trade_date,type,type_name',
 'daily':'ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount',
 'adj_factor':'ts_code,trade_date,adj_factor',
 'suspend_d':'ts_code,trade_date,suspend_timing,suspend_type',
 'stk_limit':'trade_date,ts_code,pre_close,up_limit,down_limit',
 'index_daily':'ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount',
 'anns_d':'ann_date,ts_code,name,title,url,rec_time',
}
CAPS={'stock_st':1000,'daily':6000,'adj_factor':6000,'stk_limit':6000,'suspend_d':5000,'index_daily':8000,'anns_d':2000}


def finite(value):
 return type(value) in (int,float) and math.isfinite(value)


def iso(value):
 value=str(value)
 if not re.fullmatch(r'\d{8}',value):raise ValueError('invalid provider date')
 return date.fromisoformat(value[:4]+'-'+value[4:6]+'-'+value[6:8]).isoformat()


class SourceCache:
 def __init__(self,*,directory=CACHE,token=None,url=None,frequency=2):
  self.directory=Path(directory);self.token=token or os.environ['TUSHARE_TOKEN'];self.url=url or os.environ['TUSHARE_HTTP_URL']
  self.frequency=frequency;self.lock=threading.Lock();self.next_call=0.
  (self.directory/'responses').mkdir(parents=True,exist_ok=True)
  (self.directory/'queries').mkdir(exist_ok=True)

 def query(self,api_name,params,_attempt=0):
  query={'api_name':api_name,'params':params,'fields':FIELDS[api_name],'url':self.url}
  key=digest(query);meta=self.directory/'queries'/(key+'.json')
  if meta.exists():
   ref=json.loads(meta.read_text());raw=gzip.decompress((self.directory/'responses'/(ref['response_sha256']+'.json.gz')).read_bytes())
   if ref['query']!=query or sha256(raw).hexdigest()!=ref['response_sha256']:raise ValueError('cached source identity changed')
   payload=json.loads(raw)
  else:
   # Shared reservation across workers; limits requests without serializing I/O.
   with self.lock:
    wait=max(0,self.next_call-time.monotonic());self.next_call=max(time.monotonic(),self.next_call)+1/self.frequency
   if wait:time.sleep(wait)
   body=json.dumps({**{k:v for k,v in query.items() if k!='url'},'token':self.token}).encode()
   request=Request(self.url,data=body,headers={'Content-Type':'application/json','Accept-Encoding':'gzip','User-Agent':'st-regime-authorized-materializer/1.0'})
   with urlopen(request,timeout=25) as response:
    raw=response.read()
    if str(response.headers.get('Content-Encoding','')).lower()=='gzip':raw=gzip.decompress(raw)
   if self.token.encode() in raw:raise ValueError('provider echoed credential; response not saved')
   payload=json.loads(raw)
   if int(payload.get('code') or 0)!=0:
    if '速度过快' in str(payload.get('msg')) and _attempt<3:
     time.sleep(8);return self.query(api_name,params,_attempt+1)
    safe=str(payload.get('msg') or 'provider error').replace(self.token,'[redacted]')[:180]
    raise RuntimeError(f'{api_name}: {safe}')
   ref={'version':ACQUISITION_VERSION,'query_id':key,'query':query,'response_sha256':sha256(raw).hexdigest(),'bytes':len(raw),'fetched_at':datetime.now(timezone.utc).isoformat()}
   target=self.directory/'responses'/(ref['response_sha256']+'.json.gz')
   if not target.exists():target.write_bytes(gzip.compress(raw,mtime=0))
   atomic_write_json(meta,ref)
  block=payload.get('data') or {};names=block.get('fields') or [];items=block.get('items') or []
  if len(items)>=CAPS[api_name]:raise ValueError(f'{api_name}: response reached row cap; split query before use')
  rows=[dict(zip(names,row,strict=True)) for row in items]
  return rows,ref


def unique(rows,key='ts_code'):
 result={}
 for row in rows:
  if row[key] in result:raise ValueError('duplicate provider identity')
  result[row[key]]=row
 return result


def activity_fact(member,raw,suspensions,limits):
 """An actual positive-volume quote wins over a resume/intraday event marker."""
 raw=raw or {};limit=limits or {};events=suspensions or []
 traded=all(finite(raw.get(k)) and raw[k]>0 for k in ('close','vol','pre_close')) and finite(raw.get('pct_chg'))
 full_stop=any(e.get('suspend_type')=='S' and not e.get('suspend_timing') for e in events)
 status='trading' if traded else 'suspended' if full_stop else 'unknown'
 risk=' '.join(str(member.get(k) or '') for k in ('name','risk_type','risk_type_name'))
 terminal='terminal' if '退市整理' in risk else 'not_terminal' if member.get('risk_type')=='ST' and member.get('risk_type_name')=='风险警示板' else 'unknown'
 if traded and abs((raw['close']/raw['pre_close']-1)*100-raw['pct_chg'])>.001:raise ValueError('daily return and raw reference price conflict')
 return {'symbol':member['symbol'],'trade_date':member['trade_date'],'name':member['name'],
         **{k:raw.get(k) for k in ('pct_chg','pre_close','close','high','low','amount')},'volume':raw.get('vol'),
         'turnover_rate_f':None,'suspension_status':status,'terminal_phase_status':terminal,
         'up_limit':limit.get('up_limit'),'down_limit':limit.get('down_limit'),'limit_state_conflict':False,
         'source':'tushare:stock_st+daily+suspend_d+stk_limit',
         'suspension_event_types':[r.get('suspend_type') for r in events],
         'traded_despite_suspension_event':bool(traded and events)}


def assemble(cache,calendar,baseline):
 members=[];activities=[];raw_quotes={};factors={};refs=[];day_proof=[]
 for day in calendar:
  results={api:cache.query(api,{'trade_date':day.replace('-','')}) for api in ('stock_st','daily','adj_factor','suspend_d','stk_limit')}
  refs.extend(ref for rows,ref in results.values());raw=unique(results['daily'][0]);factor=unique(results['adj_factor'][0]);limits=unique(results['stk_limit'][0]);membership=unique(results['stock_st'][0]);stops={}
  for row in results['suspend_d'][0]:
   if iso(row['trade_date'])!=day:raise ValueError('suspension outside queried day')
   stops.setdefault(row['ts_code'],[]).append(row)
  if len(raw)<4000 or len(membership)<100:raise ValueError('implausibly incomplete full-market source')
  for source in (raw,factor,limits,membership):
   if any(iso(r['trade_date'])!=day for r in source.values()):raise ValueError('provider ignored requested date')
  for code,r in membership.items():
   symbol=code.split('.')[0]
   if not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)',code):raise ValueError('invalid membership code')
   member={'trade_date':day,'symbol':symbol,'ts_code':code,'name':r['name'],'risk_type':r['type'],'risk_type_name':r['type_name'],'source':'tushare:stock_st','fetched_at':results['stock_st'][1]['fetched_at']}
   members.append(member)
   if main_board(symbol):activities.append(activity_fact(member,raw.get(code),stops.get(code),limits.get(code)))
  raw_quotes[day]=raw;factors[day]=factor
  day_proof.append({'date':day,'all_quotes':len(raw),'all_st_members':len(membership),'main_members':sum(main_board(s.split('.')[0]) for s in membership),'suspension_rows':len(results['suspend_d'][0]),'queries':{k:v[1]['query_id'] for k,v in results.items()}})
 fixed=sorted(r['ts_code'] for r in members if r['trade_date']==ANCHOR and main_board(r['symbol']))
 old_fixed=sorted(r['ts_code'] for r in baseline['members'] if r['trade_date']==ANCHOR and main_board(r['symbol']))
 if fixed!=old_fixed:raise ValueError('historical anchor membership differs; needs an explicit cohort revision')
 prices=[];quote_gaps=[]
 price_symbols=sorted(set(fixed)|{r['ts_code'] for r in members if r['trade_date']>='2026-07-06' and main_board(r['symbol'])})
 for code in price_symbols:
  observed_factors=[factors[d][code]['adj_factor'] for d in calendar if code in factors[d] and finite(factors[d][code]['adj_factor']) and factors[d][code]['adj_factor']>0]
  if not observed_factors:raise ValueError('fixed member lacks adjustment factors')
  latest=observed_factors[-1]
  for day in calendar:
   raw=raw_quotes[day].get(code);factor=factors[day].get(code)
   if raw is None:continue
   if factor is None or not finite(factor.get('adj_factor')) or factor['adj_factor']<=0:
    quote_gaps.append({'symbol':code,'date':day,'gap':'raw price without adjustment factor'});continue
   if not finite(raw.get('close')) or raw['close']<=0:continue
   prices.append({'symbol':code[:6],'trade_date':day,'close':raw['close']*factor['adj_factor']/latest,'has_trade':finite(raw.get('vol')) and raw['vol']>0,'raw_volume':raw.get('vol'),'source':'tushare:daily+adj_factor:qfq','fetched_at':next(r['fetched_at'] for r in refs if r['query']['api_name']=='daily' and r['query']['params']['trade_date']==day.replace('-',''))})
 benchmarks=[]
 for key,code in [('csi_all_share','000985.CSI'),('csi_2000','932000.CSI')]:
  rows,ref=cache.query('index_daily',{'ts_code':code,'start_date':calendar[0].replace('-',''),'end_date':calendar[-1].replace('-','')});refs.append(ref)
  for row in rows:
   benchmarks.append({'benchmark_id':key,'trade_date':iso(row['trade_date']),'close':row['close'],'pct_change':row['pct_chg'],'source':'tushare:index_daily','fetched_at':ref['fetched_at']})
 differences=[];old={(r['trade_date'],r['symbol']):r for r in baseline['activities']}
 for r in activities:
  prior=old.get((r['trade_date'],r['symbol']))
  if prior and any(prior.get(k)!=r.get(k) for k in ('pct_chg','suspension_status','terminal_phase_status')):
   differences.append({'date':r['trade_date'],'symbol':r['symbol'],'before':{k:prior.get(k) for k in ('pct_chg','suspension_status','terminal_phase_status')},'after':{k:r.get(k) for k in ('pct_chg','suspension_status','terminal_phase_status')},'traded_despite_event':r['traded_despite_suspension_event']})
 normalized={'version':VERSION,'through':calendar[-1],'calendar':calendar,'members':members,'activities':activities,'benchmarks':benchmarks,'fixed_prices':prices,'activity_snapshots':[],
  'source_tables':[{'kind':'frozen_provider_responses','version':ACQUISITION_VERSION,'responses':len(refs),'provenance_field':'refresh_provenance.original_source_refs'}],'refresh_provenance':{'version':ACQUISITION_VERSION,'through':calendar[-1],'provider_url':cache.url,'fetched_on':datetime.now(timezone.utc).isoformat(),
   'original_source_refs':refs,'day_coverage':day_proof,'fixed_quote_gaps':quote_gaps,'price_universe':'fixed_July3_plus_all_post_rule_members','price_symbols':price_symbols,'acquisition_code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'prior_input_digest':digest(baseline),'prior_activity_differences':differences,
   'normalization_note':'Positive-volume daily quotes establish trading even on resume/intraday suspension-event dates; missing quotes require explicit full-day S evidence. Daily turnover was not acquired and is null.'}}
 return normalized


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--env-file',type=Path,required=True);parser.add_argument('--through',default='2026-11-06');parser.add_argument('--cache',type=Path,default=CACHE);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=3)
 args=parser.parse_args();load_provider_env(args.env_file);cache=SourceCache(directory=args.cache)
 today=datetime.now(timezone.utc).astimezone(ZoneInfo('Asia/Shanghai')).date()
 if date.fromisoformat(args.through)>=today:raise ValueError('only completed earlier sessions may be materialized')
 calendar=sessions_2026(date(2026,5,6),date.fromisoformat(args.through))
 if not calendar or calendar[-1]!=args.through:raise ValueError('requested endpoint is not a verified trading session')
 args.output.mkdir(parents=True,exist_ok=True);baseline_path=args.output/'baseline-input.json.gz'
 if baseline_path.exists():baseline=json.loads(gzip.decompress(baseline_path.read_bytes()))
 else:
  pointer=json.loads((ROOT/'current.json').read_text());baseline=json.loads(gzip.decompress((ROOT/pointer['source_asset']).read_bytes()));baseline_path.write_bytes(gzip.compress(json.dumps(baseline,ensure_ascii=False).encode(),mtime=0));atomic_write_json(args.output/'baseline-snapshot.json',pointer)
 tasks=[(api,day) for day in calendar for api in ('stock_st','daily','adj_factor','suspend_d','stk_limit')]
 failed=[]
 with ThreadPoolExecutor(max_workers=args.workers) as pool:
  futures={pool.submit(cache.query,api,{'trade_date':day.replace('-','')}):(api,day) for api,day in tasks}
  for n,future in enumerate(as_completed(futures),1):
   api,day=futures[future]
   try:future.result()
   except Exception as error:failed.append({'api':api,'date':day,'error_type':type(error).__name__,'message':str(error).replace(cache.token,'[redacted]')[:180]})
   if n%30==0:print(json.dumps({'queries_completed':n,'total':len(tasks),'failed':len(failed)}),flush=True)
 atomic_write_json(args.output/'acquisition-failures.json',failed)
 if failed:raise RuntimeError('source queries failed; successful cache retained, retry same batch')
 inputs=assemble(cache,calendar,baseline);encoded=json.dumps(inputs,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();target=args.output/'refreshed-input.json.gz';target.write_bytes(gzip.compress(encoded,mtime=0));atomic_write_json(args.output/'acquisition-summary.json',{'through':inputs['through'],'sessions':len(calendar),'source_queries':len(tasks)+2,'input_digest':digest(inputs),'activities':len(inputs['activities']),'fixed_prices':len(inputs['fixed_prices']),'prior_activity_differences':inputs['refresh_provenance']['prior_activity_differences'],'input_asset_sha256':sha256(encoded).hexdigest()})
 print(json.dumps({'ready':True,'through':inputs['through'],'sessions':len(calendar),'input_digest':digest(inputs),'old_activity_differences':len(inputs['refresh_provenance']['prior_activity_differences'])}),flush=True)


if __name__=='__main__':main()
