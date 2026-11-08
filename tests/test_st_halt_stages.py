from copy import deepcopy
import pytest
from canonical_json import digest
from st_halt_stages import halt_stage_view,scope_digest

def fixture():
 cal=['2026-10-09','2026-10-12','2026-10-13','2026-10-14'];i={'calendar':cal,'through':cal[-1],'activities':[],'fixed_prices':[]}
 for s in ['002717','600491']:
  i['activities'] += [{'symbol':s,'trade_date':d,'suspension_status':'suspended','volume':0} for d in cal[1:]]
  i['fixed_prices'] += [{'symbol':s,'trade_date':cal[0],'has_trade':True,'close':1},{'symbol':s,'trade_date':cal[2],'has_trade':True,'close':2}]
 facts=[{'published_on':'2026-10-09','text':'verified fact','source':{'sha256':'abc','url':'https://example.test','page':1,'title':'official'}}]
 p={'scope_digest':scope_digest(i),'rows':[{'symbol':'002717','halt_on':cal[1],'resume_on':None,'facts':facts},{'symbol':'600491','halt_on':cal[1],'resume_on':cal[2],'facts':facts}]};p['content_digest']=digest(p);i['halt_stages']=p;return i

def test_open_and_closed_halts_do_not_share_inferred_resume():
 x=halt_stage_view(fixture());a,b=x['rows'];assert a['halt_market_days']==3 and a['resume_on'] is None and a['resume_has_trade'] is None;assert b['halt_market_days']==1 and b['resume_has_trade'] is True;assert a['all_halt_days_confirmed'] and b['all_halt_days_confirmed']

def test_missing_or_traded_day_exposes_unconfirmed_boundary():
 i=fixture();i['activities'][1]['volume']=10;i['halt_stages']['scope_digest']=scope_digest(i);p=i['halt_stages'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'});assert not halt_stage_view(i)['rows'][0]['all_halt_days_confirmed']

def test_source_and_scope_drift_fail_closed():
 i=fixture();i['halt_stages']['rows'][0]['resume_on']='2026-10-14'
 with pytest.raises(ValueError,match='scope changed'):halt_stage_view(i)
 i=fixture();i['activities'].pop()
 with pytest.raises(ValueError,match='scope changed'):halt_stage_view(i)

def test_optional_old_snapshots():assert halt_stage_view({}) is None
