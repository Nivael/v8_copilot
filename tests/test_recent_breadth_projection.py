import pytest
from recent_breadth_projection import combine_day,halt_coverage
DAY='2026-11-20'
def trade(last='9'):
 return {'last':last,'prev_close':'10','amount':'1000','is_trading':True}
def test_missing_price_is_not_filled_with_zero_and_halted_stock_does_not_become_flat():
 with pytest.raises(ValueError):combine_day(DAY,['600000'],{},set(),[])
 r=combine_day(DAY,['600000','600001'],{'600000':trade()}, {(DAY,'600001')},[])
 assert r['all']['listed_source_stocks']==2 and r['all']['observed_trading_stocks']==1
 assert r['all']['declining']==1 and r['all']['flat']==0 and r['all']['nontrading_stocks']==1
 assert r['missing_prices_classified_as_halted']==['600001']

def test_trading_conflict_and_quote_outside_population_fail():
 with pytest.raises(ValueError):combine_day(DAY,['600000'],{'600000':trade()},{(DAY,'600000')},[])
 with pytest.raises(ValueError):combine_day(DAY,[],{'600000':trade()},set(),[])

def row():
 return {'productCode':'600185','controlType':'TR','startStopDate':'20261112','endStopDate':'','type':'LXTP','stopTime':'','endStopReason':''}

def test_open_halt_needs_both_reviewed_start_and_independent_inactive_close():
 r=row();pop={DAY:['600185']}
 with pytest.raises(ValueError):halt_coverage([r],pop,{'600185':{'is_trading':False}},{})
 with pytest.raises(ValueError):halt_coverage([r],pop,{'600185':{'is_trading':True}},{'600185':'2026-11-12'})
 pairs,proof=halt_coverage([r],pop,{'600185':{'is_trading':False}},{'600185':'2026-11-12'})
 assert pairs=={(DAY,'600185')}and proof[0]['last_suspended_on']is None
 with pytest.raises(ValueError):halt_coverage([r,r],pop,{'600185':{'is_trading':False}},{'600185':'2026-11-12'})
