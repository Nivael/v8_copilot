import copy,json
from pathlib import Path
import pytest
from st_breadth_timing import analyze_timing

def evidence():return json.loads((Path(__file__).resolve().parents[1]/'ST_BREADTH_ALIGNMENT_EVIDENCE_2026_11_21.json').read_text())

def test_real_three_close_moves_and_preceding_anchor():
 r=analyze_timing(evidence())['rows'];assert len(r)==3
 assert r[-1]['anchor']=='2026-11-11';assert r[-1]['signal_date']=='2026-11-16'
 assert r[-1]['already_st_pct']==pytest.approx(-5.590081184432938)
 assert r[-1]['following']['observed_following_sessions']==3

def test_future_prices_cannot_change_already_observed_move():
 e=evidence();old=analyze_timing(e)['rows'][-1];alter=copy.deepcopy(e)
 for r in alter['inputs']['extension_days']:
  if r['date']>old['signal_date']:r['return_pct']=10
 from st_breadth_alignment import analyze
 i=alter['inputs'];alter['reading']=analyze({'daily':i['daily'],'themes':{'current_extension':{'days':i['extension_days']}}},{'sequence':{'days':i['breadth_days']}})
 new=analyze_timing(alter)['rows'][-1];assert old['already_st_pct']==new['already_st_pct'];assert old['following']!=new['following']

def test_mismatched_frozen_input_stops():
 e=evidence();e['reading']['signals'][0]['st_pct']=0
 with pytest.raises(ValueError):analyze_timing(e)
