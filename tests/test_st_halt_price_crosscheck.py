from copy import deepcopy
from hashlib import sha256
import json
import pytest
from canonical_json import digest
from st_halt_price_crosscheck import halt_price_check_view,scope_digest

def fixture():
 cal=['2026-07-02','2026-07-03','2026-07-06'];i={'calendar':cal,'through':cal[-1],'fixed_prices':[],'activities':[],'benchmarks':[],'announcement_study':{'verified_events':[{'symbol':'002717','id':'event','title':'event','published_on':'2026-07-03'}]}};companies=[];sources=[]
 for s in ['600491','002717']:
  rows=[{'date':d,'raw_close':1.,'volume':0 if d==('2026-07-03' if s=='600491' else '2026-07-06') else 100,'adj_factor':1.,'qfq_close':1.,'suspension_records':[]} for d in cal]
  for r in rows:r['has_trade']=r['volume']>0
  companies.append({'symbol':s,'qfq_normalization_date':cal[-1],'qfq_normalization_factor':1.,'rows':rows})
  for key in ['tencent_raw','tencent_qfq','eastmoney_raw','eastmoney_qfq']:
   qs=[[r['date'],'1.00','1.00','1.00','1.00','100'] for r in rows if r['has_trade']];ticker=('sh' if s.startswith('6') else 'sz')+s
   x={'data':{ticker:{'qt':{ticker:['name','name',s]},'day':qs,'qfqday':qs}}} if key.startswith('tencent') else {'data':{'code':s,'market':1 if s.startswith('6') else 0,'klines':[','.join(r) for r in qs]}}
   raw=json.dumps(x);sources.append({'symbol':s,'key':key,'raw_text':raw,'sha256':sha256(raw.encode()).hexdigest(),'url':'https://example.test','observed_at':'2026-11-09'})
 p={'scope_digest':scope_digest(i),'original_prices':{'calendar':cal,'through':cal[-1],'companies':companies},'sources':sources,'resolved_retries':[],'failed_requests':[]};p['content_digest']=digest(p);i['halt_price_crosscheck']=p;daily=[{'date':d,'market_pct':1.,'return_pct':2.} for d in cal];return i,daily

def test_missing_start_and_missing_end_keep_distinct_alternative_dates():
 i,d=fixture();v=halt_price_check_view(i,d);a,b=v['rows'];assert a['full_window']['stock_pct'] is None and a['alternative_actual_period']['anchor']=='2026-07-02';assert b['full_window']['stock_pct'] is None and b['alternative_actual_period']['through']=='2026-07-03';assert v['all_available_prices_agree'] and v['quote_points']==16

def test_mutated_sources_scope_or_partial_channels_fail_closed():
 i,d=fixture();i['halt_price_crosscheck']['sources'].pop();p=i['halt_price_crosscheck'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})
 with pytest.raises(ValueError,match='channels incomplete'):halt_price_check_view(i,d)
 i,d=fixture();i['fixed_prices'].append({'changed':True})
 with pytest.raises(ValueError,match='scope changed'):halt_price_check_view(i,d)

def test_optional_old_data():assert halt_price_check_view({},[]) is None
