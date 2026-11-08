from copy import deepcopy
import pytest
from st_membership_audit import issuer_followup_view

def fixture():
 source={'sha256':'abc','url':'https://example.test','title':'official','page':1}
 h={'period_start':'2026-01-01','period_end':'2026-06-30','published_on':'2026-08-22','currency':'CNY','unit':'yuan','audited':False,'revenue':'100.00','parent_profit':'-10.00','operating_cash':'5.00','parent_equity':'-100.00','source':source}
 q={**h,'period_end':'2026-09-30','published_on':'2026-10-23','revenue':'300.00','parent_profit':'-30.00','operating_cash':'8.00','parent_equity':'-120.00'}
 f={'as_of':'2026-11-06','reports':[h,q],'reported_single_quarter':{'revenue':'200.00','parent_profit':'-20.00'},'cash_rollforward':{'opening_yuan':'20.00','net_change_yuan':'-2.00','closing_yuan':'18.00'},'prior_unfreeze_entity':'石岛玻璃','new_freeze':{'entity':'安庆华鹏','published_on':'2026-10-28','account_count':4,'accounts':[{'amount_yuan':str(n)} for n in (1,2,3,4)],'frozen_yuan':'10.00'},'facts':[{'published_on':'2026-10-28','document_dated_on':'2026-10-27','source':source}]}
 return {'anchor':'2026-07-03','followup':f},{'through':'2026-11-06'}

def test_same_basis_quarter_and_cash_reconcile_without_mutating_historical_packet():
 c,i=fixture();before=deepcopy(c);r=issuer_followup_view(c,i);assert r['quarter_revenue_yuan']=='200.00' and r['quarter_parent_profit_yuan']=='-20.00';assert c==before and r['cash_rollforward']['closing_yuan']=='18.00'

def test_incompatible_periods_units_or_reported_quarter_are_rejected():
 for field,value in [('unit','wanyuan'),('period_start','2026-07-01'),('audited',True),('published_on','2026-11-07')]:
  c,i=fixture();c['followup']['reports'][1][field]=value
  with pytest.raises(ValueError,match='period/unit/audit'):issuer_followup_view(c,i)
 c,i=fixture();c['followup']['reported_single_quarter']['parent_profit']='-30'
 with pytest.raises(ValueError,match='cumulative difference'):issuer_followup_view(c,i)

def test_subsidiary_scope_future_fact_and_totals_cannot_be_silently_combined():
 c,i=fixture();c['followup']['new_freeze']['entity']='石岛玻璃'
 with pytest.raises(ValueError,match='entity/count/amount'):issuer_followup_view(c,i)
 c,i=fixture();c['followup']['new_freeze']['frozen_yuan']='9'
 with pytest.raises(ValueError,match='entity/count/amount'):issuer_followup_view(c,i)
 c,i=fixture();c['followup']['cash_rollforward']['closing_yuan']='19'
 with pytest.raises(ValueError,match='rollforward'):issuer_followup_view(c,i)
 c,i=fixture();c['followup']['facts'][0]['published_on']='2026-11-07'
 with pytest.raises(ValueError,match='timely'):issuer_followup_view(c,i)

def test_absent_followup_is_compatible():assert issuer_followup_view({}, {}) is None
