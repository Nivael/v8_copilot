import pytest
from canonical_json import digest
from st_company_risk_cases import company_risk_case_view,scope_digest

def fixture():
 source={'sha256':'abc','url':'https://example.test','page':1,'title':'report'}
 financial={'period_start':'2026-01-01','period_end':'2026-09-30','published_on':'2026-10-31','unit':'yuan','currency':'CNY','audited':False,'revenue':'100','parent_profit':'-10','operating_cash':'-20','parent_equity':'1000','source':source}
 i={'calendar':['2026-07-03','2026-11-06'],'through':'2026-11-06','benchmarks':[],'fixed_prices':[{'symbol':s,'trade_date':d,'close':v,'has_trade':True} for s in ('600730','603021') for d,v in [('2026-07-03',10),('2026-11-06',5)]]}
 h={**financial,'published_on':'2026-10-23','operating_cash':'20','parent_equity':'-100'};i['official_membership_audit']={'issuer_checks':[{'symbol':'603021','followup':{'reports':[h]}}]}
 p={'symbol':'600730','through':i['through'],'criminal':{'scope':'individuals','status':'investigation','final_disposition':None},'civil':{'original_case_id':'case','revoked_case_id':'case','first_published_on':'2026-07-15','revocation_received_on':'2026-07-15','revocation_published_on':'2026-07-17','final_merits_judgment':None},'facts':[{'published_on':'2026-07-17','document_dated_on':'2026-07-17','source':source}],'financial':financial,'warning':{'cause':'亏损与收入条件'}};p['scope_digest']=scope_digest(i);i['gaoke_risk_case']=p;seal(i)
 return i,[{'date':'2026-11-06','market_pct':-20,'return_pct':-10}]
def seal(i):p=i['gaoke_risk_case'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})

def test_two_independent_companies_keep_different_risk_axes_and_same_window():
 i,daily=fixture();x=company_risk_case_view(i,daily);a,b=x['comparison'];assert a['financial']['parent_equity']=='1000' and b['financial']['parent_equity']=='-100';assert a['price_window']==b['price_window'];assert a['price_window']['stock_pct']==-50;assert x['independent_companies']==2;assert x['criminal']['final_disposition'] is None and x['civil']['final_merits_judgment'] is None

def test_wrong_proceeding_or_unverified_final_stage_is_rejected():
 for kind,field,value in [('criminal','scope','issuer'),('criminal','final_disposition','convicted'),('civil','revoked_case_id','other'),('civil','revocation_received_on','2026-07-18')]:
  i,d=fixture();i['gaoke_risk_case'][kind][field]=value;seal(i)
  with pytest.raises(ValueError,match='stage|identity'):company_risk_case_view(i,d)

def test_comparison_period_units_source_and_missing_endpoint_are_explicit():
 i,d=fixture();i['gaoke_risk_case']['financial']['period_end']='2026-06-30';seal(i)
 with pytest.raises(ValueError,match='incomparable'):company_risk_case_view(i,d)
 i,d=fixture();i['official_membership_audit']['issuer_checks'][0]['followup']['reports'][0]['unit']='wanyuan'
 with pytest.raises(ValueError,match='scope changed'):company_risk_case_view(i,d)
 i,d=fixture();i['fixed_prices'][1]['has_trade']=False;i['gaoke_risk_case']['scope_digest']=scope_digest(i);seal(i);x=company_risk_case_view(i,d);assert x['comparison'][0]['price_window']['stock_pct'] is None and x['comparison'][1]['price_window']['stock_pct']==-50

def test_optional_old_snapshots():assert company_risk_case_view({},[]) is None

def subsidiary_fixture():
 i,d=fixture();p=i['gaoke_risk_case'];p['name']='*ST高科';p['open_catalog_items']=[]
 p['civil']['source']={'url':'https://example.test/parent','title':'parent','page':1,'sha256':'parent'}
 p['subsidiary_civil']={'entity':'广西英腾教育科技股份有限公司','short_name':'英腾教育','court':'柳州市鱼峰区人民法院','case_id':'subsidiary','released_case_id':'subsidiary','first_published_on':'2026-07-22','original_received_on':None,'release_received_on':'2026-07-23','release_published_on':'2026-07-25','restraint_duration_days':None,'final_merits_judgment':None,'release_scope':'all_behaviour_measures_in_this_case','reconsideration_at_first_disclosure':'planned_not_proven_submitted','requests':[{'key':k} for k in ('execute_resolution','hold_shareholder_meeting','registration','appointments_rewards')],'order_items':[{'key':k} for k in ('execute_resolution','registration','appointments_rewards')],'facts':[{'published_on':'2026-07-25','source':{'url':'https://example.test/subsidiary','title':'release','page':1,'sha256':'sub'}}]};seal(i);return i,d

def test_distinct_civil_cases_and_request_order_stages_do_not_collapse():
 i,d=subsidiary_fixture();s=company_risk_case_view(i,d)['subsidiary_civil'];assert [r['case_id'] for r in s['procedure_rows']]==['case','subsidiary'];assert s['release_received_on']=='2026-07-23' and s['release_published_on']=='2026-07-25';assert len(s['requests'])==4 and len(s['order_items'])==3;assert s['restraint_duration_days'] is None and s['final_merits_judgment'] is None

def test_subsidiary_case_dates_and_unproven_submission_or_finality_fail_closed():
 for field,value in [('case_id','case'),('release_received_on','2026-07-26'),('restraint_duration_days',3),('final_merits_judgment','won'),('reconsideration_at_first_disclosure','submitted')]:
  i,d=subsidiary_fixture();i['gaoke_risk_case']['subsidiary_civil'][field]=value;seal(i)
  with pytest.raises(ValueError):company_risk_case_view(i,d)
 i,d=subsidiary_fixture();i['gaoke_risk_case']['open_catalog_items']=[{'title':'already verified'}];seal(i)
 with pytest.raises(ValueError,match='still marked unread'):company_risk_case_view(i,d)
 i,d=subsidiary_fixture();s=i['gaoke_risk_case']['subsidiary_civil'];s['order_items'][-1]['key']='hold_shareholder_meeting';seal(i)
 with pytest.raises(ValueError,match='requests mistaken'):company_risk_case_view(i,d)
