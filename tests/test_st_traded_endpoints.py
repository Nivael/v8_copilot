from copy import deepcopy
import pytest
from st_regime_comparison import endpoint_trade_state,build
from test_st_regime_comparison import synthetic_inputs

def test_positive_price_does_not_establish_trade_and_conflicts_are_not_hidden():
 assert endpoint_trade_state({'close':1},None)['status']=='unknown'
 assert endpoint_trade_state({'close':1,'has_trade':False,'raw_volume':0},None)['status']=='not_traded'
 assert endpoint_trade_state({'close':1,'has_trade':True,'raw_volume':10},{'suspension_status':'suspended'})['status']=='conflict'
 assert endpoint_trade_state({'close':1,'has_trade':False,'raw_volume':0},{'suspension_status':'trading','volume':10})['status']=='conflict'
 assert endpoint_trade_state(None,None)['status']=='missing_price'

def test_suspension_keeps_reference_return_but_removes_primary_and_paired_return():
 i=synthetic_inputs()
 for field in ('members','activities','fixed_prices'):
  i[field].extend([{**r,'symbol':'600002'} for r in i[field] if r['symbol']=='600001'])
 old=build(i);price=next(r for r in i['fixed_prices'] if r['trade_date']=='2026-07-03');price.update(has_trade=False,raw_volume=0)
 act=next(r for r in i['activities'] if r['trade_date']=='2026-07-03');act.update(suspension_status='suspended',volume=0,pct_chg=None,close=price['close'])
 v=build(i)
 for c,o in zip(v['comparisons'],old['comparisons']):
  assert c['fixed_after']['covered']==1 and c['fixed_after']['total']==2 and c['paired']['count']==1
  assert c['fixed_after']['reference_summary']['covered']==2
  row=c['fixed_after']['rows'][0];assert row['return_pct'] is None and row['market_excess_pp'] is None
  assert row['reference_return_pct']==o['fixed_after']['rows'][0]['return_pct']
  assert row['endpoint_trade_states']['anchor']['status']=='not_traded'
  assert c['reference_paired']['count']==2
