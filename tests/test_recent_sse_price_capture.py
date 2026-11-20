from datetime import date
import json
import pytest
from market_calendar import sessions_2026
from recent_sse_price_capture import capture

def basis():
 cal=sessions_2026(date(2026,11,9),date(2026,11,20));codes=['600000','600001']
 return {'window':{'start':cal[0],'end':cal[-1]},'pool':dict.fromkeys(codes,{}),'populations':{d:codes for d in cal},'basis_capture_digest':'a'*64},cal

def response(code,cal):
 return json.dumps({'code':code,'total':len(cal),'begin':0,'end':len(cal),'kline':[[int(d.replace('-','')),10,10,0,100,1000] for d in cal]}).encode()

def test_resume_replays_originals_and_does_not_request_again(tmp_path):
 b,cal=basis();calls=[]
 def get(c):calls.append(c);return response(c,cal)
 first=capture(b,tmp_path,get,workers=1);assert len(calls)==2 and first['status']=='captured'
 refs=first['source_refs'];second=capture(b,tmp_path,lambda c:pytest.fail('must reuse'),workers=1)
 assert second['source_refs']==refs
 assert json.loads((tmp_path/'progress.json').read_text())['reused']==2

def test_failed_member_stays_partial_then_only_missing_member_is_requested(tmp_path):
 b,cal=basis()
 def get(c):
  if c=='600001':raise TimeoutError()
  return response(c,cal)
 assert capture(b,tmp_path,get,workers=1)['status']=='partial';assert not(tmp_path/'complete.json').exists()
 calls=[]
 def repair(c):calls.append(c);return response(c,cal)
 assert capture(b,tmp_path,repair,workers=1)['status']=='captured';assert calls==['600001']

def test_changed_plan_and_tampered_cached_source_are_not_silently_replaced(tmp_path):
 b,cal=basis();result=capture(b,tmp_path,lambda c:response(c,cal),workers=1)
 bad=tmp_path/(result['source_refs'][0]['sha256']+'.raw');bad.write_bytes(b'changed')
 result=capture(b,tmp_path,lambda c:pytest.fail('do not replace cache'),workers=1)
 assert result['status']=='partial' and bad.read_bytes()==b'changed'
 b['basis_capture_digest']='b'*64
 with pytest.raises(ValueError):capture(b,tmp_path,lambda c:response(c,cal),workers=1)
