from copy import deepcopy
from datetime import date
import pytest
from market_calendar import sessions_2026
from market_breadth_sequence import analyze

def inputs():
 cal=sessions_2026(date(2026,9,4),date(2026,9,30))
 points=[{'date':d,'all':{'observed_trading_stocks':10,'advancing':4 if i<5 or 6<=i<=8 else 6,'declining':5 if i<5 or 6<=i<=8 else 3,'flat':1,'declining_5pct_or_more':2}} for i,d in enumerate(cal[:11])]
 return {'availability':'observed','complete_market_history':True,'start':cal[0],'through':cal[10],'points':points,'content_digest':'a'*64},{'calendar':cal,'indices':{'000985.CSI':[{'trade_date':d,'close':100+i} for i,d in enumerate(cal)]},'content_digest':'b'*64,'through':cal[-1]}

def test_long_streak_is_one_episode_and_future_price_never_changes_signal():
 h,i=inputs();before=deepcopy(h);r=analyze(h,i)
 assert len(r['signals'])==2 and [s['date'] for s in r['signals']]==[h['points'][2]['date'],h['points'][8]['date']]
 assert r['signals'][0]['left_boundary_unknown'] and not r['signals'][1]['left_boundary_unknown']
 assert r['signals'][0]['after_five_on']==i['calendar'][7]
 for p in i['indices']['000985.CSI'][11:]:p['close']=50
 other=analyze(h,i)
 assert [s['date'] for s in other['signals']]==[s['date'] for s in r['signals']]
 assert other['signals'][1]['after_five_market_pct']!=r['signals'][1]['after_five_market_pct']
 assert h==before

def test_half_is_not_below_half_and_no_incomplete_outcome_is_filled():
 h,i=inputs();h['points'][1]['all'].update(advancing=5,declining=4)
 r=analyze(h,i);assert r['days'][1]['streak']==0
 i['calendar']=i['calendar'][:11];i['indices']['000985.CSI']=i['indices']['000985.CSI'][:11]
 assert analyze(h,i)['signals'][-1]['after_five_market_pct'] is None

@pytest.mark.parametrize('change',['breadth_gap','benchmark_gap','denominator','single_venue','nan'])
def test_unsupported_inputs_are_not_bridged_or_scored(change):
 h,i=inputs()
 if change=='breadth_gap':h['points'].pop(4)
 elif change=='benchmark_gap':i['calendar'].pop(4);i['indices']['000985.CSI'].pop(4)
 elif change=='denominator':h['points'][0]['all']['flat']=2
 elif change=='single_venue':h['complete_market_history']=False
 else:i['indices']['000985.CSI'][0]['close']=float('nan')
 with pytest.raises(ValueError):analyze(h,i)
