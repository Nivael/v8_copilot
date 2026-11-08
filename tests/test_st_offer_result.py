from decimal import Decimal
import pytest
from st_halt_stages import offer_result_view

def result():return {'result_on':'2026-08-28','halt_on':'2026-08-27','resume_on':'2026-08-28','planned_shares':91786000,'accepted_shares':418699,'price_per_share':'1.25','settlement_status':'arranged_not_confirmed','completion_receipt':None,'facts':[{'published_on':'2026-08-28','source':{'sha256':'abc','url':'https://example.test','page':1,'title':'result'}}]}
def view(r):return offer_result_view(r,{'through':'2026-11-06','calendar':['2026-08-27','2026-08-28']},{('600491','2026-08-27'):{'suspension_status':'suspended','volume':0}},{('600491','2026-08-28'):{'has_trade':True}})
def test_quantity_and_price_do_not_establish_settlement():
 x=view(result());assert x['accepted_price_consideration']=='523373.75' and x['planned_consideration']=='114732500.00';assert x['accepted_to_planned_pct']==pytest.approx(float(Decimal(418699)/91786000*100));assert x['settlement_status']=='arranged_not_confirmed' and x['completion_receipt'] is None;assert x['halt_market_days']==1 and x['resume_has_trade'] is True

def test_completion_requires_receipt_and_bad_quantities_are_rejected():
 r=result();r['settlement_status']='confirmed_complete'
 with pytest.raises(ValueError,match='lacks receipt'):view(r)
 r=result();r['accepted_shares']=91786001
 with pytest.raises(ValueError,match='quantity'):view(r)
 r=result();r['result_on']='2026-11-07'
 with pytest.raises(ValueError,match='timeline'):view(r)

def test_optional_old_data():assert offer_result_view(None,{}, {},{}) is None

def completed():
 r=result();source={'sha256':'receipt','url':'https://example.test/completed','page':1,'title':'completion'};r['facts'].append({'published_on':'2026-09-02','source':source});r['settlement_status']='confirmed_complete';r['completion_receipt']={'published_on':'2026-09-02','completed_by':'2026-09-02','exact_completion_on':None,'final_shares':418699,'reported_pct':'0.0274','settlement_complete':True,'control_changed':False,'source':source};return r

def test_completion_is_disclosure_bound_not_exact_transfer_day():
 x=view(completed());assert x['completion_receipt']['completed_by']=='2026-09-02' and x['completion_receipt']['exact_completion_on'] is None;assert x['result_on']=='2026-08-28' and x['facts'][0]['published_on']=='2026-08-28'

def test_completion_rejects_unbound_future_or_conflicting_receipts():
 r=completed();r['completion_receipt']['published_on']='2026-11-07'
 with pytest.raises(ValueError,match='publication'):view(r)
 r=completed();r['completion_receipt']['final_shares']=91786000
 with pytest.raises(ValueError,match='quantity'):view(r)
 r=completed();r['completion_receipt']['source']['sha256']='changed';r['facts'][-1]['source']={**r['facts'][-1]['source'],'sha256':'receipt'}
 with pytest.raises(ValueError,match='bound to facts'):view(r)
 r=completed();r['completion_receipt']['exact_completion_on']='2026-09-02'
 with pytest.raises(ValueError,match='publication'):view(r)
