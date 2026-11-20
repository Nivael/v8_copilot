from copy import deepcopy
from datetime import date,timedelta
import json
import pytest
import st_removal_mature_windows as module
from canonical_json import digest
from hashlib import sha256

def sample():
 dates=[];d=date(2026,7,6)
 while len(dates)<21:
  if d.weekday()<5:dates.append(d.isoformat())
  d+=timedelta(days=1)
 prices=[];sources=[];events=[]
 for n in range(12):
  code=f'{n:06d}';prices.extend([{'symbol':code,'trade_date':dates[0],'close':1,'has_trade':True,'raw_volume':1},{'symbol':code,'trade_date':dates[-1],'close':2,'has_trade':True,'raw_volume':1}])
  text=json.dumps({'data':{code:{'qfqday':[[dates[0],'1','1.01'if n==11 else'1','1','1','1'],[dates[-1],'2','2','2','2','1']]}}});sources.append({'symbol':code,'provider_key':code,'text':text,'sha256':sha256(text.encode()).hexdigest(),'url':'https://example.test/'+code})
  old={'status':'valid','stock_pct':100,'through':dates[-1]}if n<10 else{'status':'insufficient_followup','stock_pct':None,'through':None}
  events.append({'era':'post','symbol':code,'name':code,'resume_close_on':dates[0],'windows':{'20':{'from_resume_close':old}}})
 text=json.dumps({'data':[{'tradeDate':d.replace('-',''),'close':1}for d in dates]});official={'key':'000985','text':text,'sha256':sha256(text.encode()).hexdigest()}
 inputs={'current_extension':{'market_inputs':{'calendar':dates,'fixed_prices':prices,'benchmarks':[{'benchmark_id':'csi_all_share','trade_date':d,'close':1}for d in dates]}},'endpoint_selection_audit':{'sources':sources},'initial_twentyseventh_four':{'cross_sources':[official]}}
 return inputs,{'rows':events}

def test_mature_does_not_promote_conflicting_price_and_old_ten_remain_identical():
 inputs,prior=sample();result=module.calculate_mature_windows(inputs,prior)
 assert result['summary']['mature']==12 and result['summary']['direct_verified']==11
 assert result['rows'][-1]['certified_stock_pct']is None and result['rows'][-1]['status']=='price_conflict'
 assert result['rows'][-2]['newly_mature']is True

def test_checks_raw_source_hash_instead_of_trusting_parsed_numbers():
 inputs,prior=sample();inputs['endpoint_selection_audit']['sources'][0]['text']+=' '
 with pytest.raises(AssertionError):module.calculate_mature_windows(inputs,prior)

def test_packet_replay_rejects_source_and_resealed_result_changes(monkeypatch):
 inputs,prior=sample();result=module.calculate_mature_windows(inputs,prior);scope={'market':inputs['current_extension']['market_inputs'],'cross':inputs['endpoint_selection_audit']['sources'],'official':inputs['initial_twentyseventh_four']['cross_sources'],'prior':prior};monkeypatch.setattr(module,'SCOPE_DIGEST',digest(scope));monkeypatch.setattr(module,'RESULT_DIGEST',digest(result));packet={'version':1,'result':result};packet['content_digest']=digest(packet);inputs['removal_mature_windows']=packet
 assert module.removal_mature_windows(inputs,prior)==result
 changed=deepcopy(inputs);changed['removal_mature_windows']['result']['summary']['direct_verified']=12;changed['removal_mature_windows']['content_digest']=digest({k:v for k,v in changed['removal_mature_windows'].items()if k!='content_digest'})
 with pytest.raises(ValueError,match='result changed'):module.removal_mature_windows(changed,prior)
 changed=deepcopy(inputs);changed['current_extension']['market_inputs']['calendar'].pop()
 with pytest.raises(ValueError,match='sources changed'):module.removal_mature_windows(changed,prior)

def test_absent_packet_preserves_older_snapshots():assert module.removal_mature_windows({},None)is None
