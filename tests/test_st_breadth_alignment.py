import pytest
from st_breadth_alignment import analyze

def inputs():
 dates=['2026-11-09','2026-11-10','2026-11-11','2026-11-12','2026-11-13','2026-11-16','2026-11-17','2026-11-18']
 daily=[{'date':d,'missing':[],'observed_count':1,'return_pct':-1,'market_pct':1} for d in dates]
 st={'daily':daily[:4],'themes':{'current_extension':{'days':daily[4:]}}}
 b={'sequence':{'days':[{'date':d,'trading':10,'advancing':4} for d in dates]}}
 return st,b

def test_long_streak_once_and_five_day_compound():
 st,b=inputs();r=analyze(st,b);assert len(r['signals'])==1
 s=r['signals'][0];assert s['date']=='2026-11-11';assert s['complete_five']
 assert s['five_st_pct']==pytest.approx((.99**5-1)*100)
 assert s['five_market_pct']==pytest.approx((1.01**5-1)*100)

def test_partial_window_not_filled_from_future_breadth():
 st,b=inputs();st['themes']['current_extension']['days']=st['themes']['current_extension']['days'][:2]
 s=analyze(st,b)['signals'][0];assert s['observed_following_sessions']==3;assert s['five_st_pct']is None;assert not s['complete_five']

def test_half_boundary_and_duplicate_or_missing_rejected():
 st,b=inputs();b['sequence']['days'][2]['advancing']=5
 assert analyze(st,b)['signals'][0]['date']=='2026-11-16'
 st['daily'].append(st['daily'][0])
 with pytest.raises(ValueError):analyze(st,b)

def test_unresolved_coverage_and_nonfinite_rejected():
 st,b=inputs();st['daily'][0]['missing']=['x']
 with pytest.raises(ValueError):analyze(st,b)
 st,b=inputs();st['daily'][0]['return_pct']=float('nan')
 with pytest.raises(ValueError):analyze(st,b)

def test_saved_source_regression_and_immature_nulls():
 import json
 from pathlib import Path
 e=json.loads((Path(__file__).resolve().parents[1]/'ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text())
 i=e['inputs'];st={'daily':i['daily'],'themes':{'current_extension':{'days':i['extension_days']}}};b={'sequence':{'days':i['breadth_days']}}
 assert analyze(st,b)==e['reading']
 assert len(e['reading']['signals'])==3
 assert e['reading']['signals'][-1]['five_market_pct'] is None
