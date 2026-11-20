from datetime import date
from copy import deepcopy
import pytest
from market_calendar import sessions_2026
from build_recent_breadth import append_history,payload

def inputs():
 cal=sessions_2026(date(2026,11,9),date(2026,11,20));points=[]
 for i,d in enumerate(cal):
  a={'listed_source_stocks':10,'observed_trading_stocks':10,'nontrading_stocks':0,'advancing':6 if i<3 else 4,'declining':3 if i<3 else 5,'flat':1,'declining_5pct_or_more':2,'median_return_pct':-1}
  points.append({'date':d,'all':a,'missing_prices_classified_as_halted':[]})
 old={'availability':'observed','start':cal[0],'through':cal[2],'points':points[:3],'base_reference_digest':'a'*64}
 recent={'complete_market_history':True,'start':cal[3],'through':cal[-1],'points':points[3:],'sources':{'source':'b'*64},'price_source_count':2,'historical_pool':2,'endpoint_members':2,'sse_archive_summary':{'start':cal[0],'through':cal[-1]}}
 ic=sessions_2026(date(2026,11,6),date(2026,11,20));index={'calendar':ic,'indices':{'000985.CSI':[{'trade_date':d,'close':100-i}for i,d in enumerate(ic)]},'through':ic[-1],'content_digest':'c'*64}
 return old,recent,index

def test_append_keeps_old_rows_and_latest_signal_remains_partial_with_four_following_sessions():
 old,recent,index=inputs();before=deepcopy(old);merged=append_history(old,recent,'d'*64);r=payload(merged,recent,index)
 assert old==before and merged['points'][:3]==old['points']
 assert r['sequence']['signals'][-1]['date']=='2026-11-16'
 assert r['sequence']['signals'][-1]['after_five_market_pct']is None
 assert r['latest_signal_observed_following_sessions']==4 and r['latest_signal_partial_through']=='2026-11-20'
 assert r['rows'][-1]['streak']==7

@pytest.mark.parametrize('change',['gap','duplicate','single_venue'])
def test_incomplete_or_overlapping_history_never_becomes_continuous(change):
 old,recent,_=inputs()
 if change=='gap':recent['points'].pop(1)
 elif change=='duplicate':recent['points'].insert(0,old['points'][-1])
 else:recent['complete_market_history']=False
 with pytest.raises(ValueError):append_history(old,recent,'d'*64)
