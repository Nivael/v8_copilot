from datetime import date,timedelta
from hashlib import sha256
import json
import pytest
from canonical_json import digest
from st_removal_followup import removal_followup_view,scope_digest
from st_halt_price_crosscheck import scope_digest as quote_scope

def fixture():
 start=date(2026,5,6);end=date(2026,11,6);cal=[(start+timedelta(days=n)).isoformat() for n in range((end-start).days+1) if (start+timedelta(days=n)).weekday()<5]
 source={'url':'https://example.test/official.pdf','title':'official','page':1,'sha256':'a'*64}
 i={'calendar':cal,'through':cal[-1],'fixed_prices':[],'benchmarks':[],'activities':[],'member_transitions':{'rows':[{'symbol':'000711','effective_on':'2026-08-31','suspend_on':'2026-08-28'}]},'announcement_study':{'verified_events':[]}}
 rows=[{'date':d,'raw_close':None if d=='2026-08-28' else 1.,'qfq_close':None if d=='2026-08-28' else 1.,'volume':0 if d=='2026-08-28' else 100,'has_trade':d!='2026-08-28','adj_factor':1.,'suspension_records':[]} for d in cal]
 qs=[[r['date'],'1','1','1','1','100'] for r in rows if r['has_trade']];raw=json.dumps({'data':{'sz000711':{'qt':{'sz000711':['name','name','000711']},'day':qs,'qfqday':qs}}})
 prices={'original_prices':{'calendar':cal,'through':cal[-1],'companies':[{'symbol':'000711','rows':rows,'qfq_normalization_date':cal[-1],'qfq_normalization_factor':1.}]},'scope_digest':quote_scope(i),'sources':[{'symbol':'000711','key':key,'raw_text':raw,'sha256':sha256(raw.encode()).hexdigest(),'url':'https://example.test/quote','observed_at':'2026-11-09'} for key in ('tencent_raw','tencent_qfq')],'resolved_retries':[],'failed_requests':[]};prices['content_digest']=digest(prices)
 def report(end,pub,rev,profit,deduct,cash):
  return {'period_start':'2026-01-01','period_end':end,'published_on':pub,'source':{**source,'published_on':pub},'audited':False,'unit':'yuan','currency':'CNY','revenue':rev,'previous_revenue':'100','revenue_yoy_pct':'0' if rev=='100' else '200','parent_profit':profit,'deducted_profit':deduct,'operating_cash':cash,'parent_equity':'10'}
 p={'symbol':'000711','legal_name':'issuer','through':cal[-1],'scope_digest':scope_digest(i),'warning':{'application_published_on':'2026-08-25','removal_published_on':'2026-08-28','effective_on':'2026-08-31','suspend_on':'2026-08-28','application_approved_at_that_time':False,'exact_approval_on':None,'limit_after_pct':10},'reports':[report('2026-06-30','2026-08-20','100','1','0.5','-1'),report('2026-09-30','2026-10-23','300','2','1','-4')],'compensation':{'received_before_last_yuan':'1','last_received_yuan':'2','total_received_yuan':'3','status':'fully_received','current_year_profit_equal_receipts':False,'commitment_2026_met':None},'auction':{'status':'repriced_not_completed','actual_receipts_yuan':None,'actual_confirmed_loss_yuan':None,'conditional_disposal_loss_yuan':'5','previous_conditional_loss_yuan':'3','previous_start_yuan':'3','new_start_yuan':'1'},'recovery':{'final_judgment':None,'received_confirmed_yuan':None},'cash_rollforward':{'operating_yuan':'-4','investing_yuan':'0','financing_yuan':'3','fx_yuan':'0','change_yuan':'-1','opening_yuan':'2','closing_yuan':'1'},'q3_reported_single':{'revenue':'200','parent_profit':'1','deducted_profit':'0.5'},'nonrecurring':{'year_to_date_yuan':'1'},'facts':[],'price_check':prices,'event_ids':['new']}
 i['jinglan_followup']=p;seal(i)
 return i,[{'date':d,'market_pct':0.,'return_pct':0.} for d in cal]
def seal(i):
 p=i['jinglan_followup'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})

def test_market_day_windows_keep_halt_and_distinct_resume_close():
 i,d=fixture();v=removal_followup_view(i,d);w=v['price_windows'];assert w['after20']['market_days']==20 and w['after20']['stock_traded_days']==19;assert w['pre_halt_to_cutoff']['anchor']=='2026-08-27' and w['first_resume_close_to_cutoff']['anchor']=='2026-08-31';assert v['single_quarter']['operating_cash']=='-3';assert not v['quotes']['all_available_prices_agree'];assert v['financial_checks']['financial_truth_verified'] is False

@pytest.mark.parametrize('area,key,value',[('auction','actual_confirmed_loss_yuan','5'),('compensation','current_year_profit_equal_receipts',True),('compensation','commitment_2026_met',True),('recovery','received_confirmed_yuan','1')])
def test_unverified_completion_and_incomparable_commitment_do_not_pass(area,key,value):
 i,d=fixture();i['jinglan_followup'][area][key]=value;seal(i)
 with pytest.raises(ValueError):removal_followup_view(i,d)

def test_cash_rollforward_cannot_be_replaced_by_profit():
 i,d=fixture();i['jinglan_followup']['cash_rollforward']['change_yuan']='2';seal(i)
 with pytest.raises(ValueError,match='cash rollforward'):removal_followup_view(i,d)

def test_changed_original_scope_cannot_be_certified():
 i,d=fixture();i['fixed_prices'].append({'symbol':'000711','trade_date':'2026-09-01','close':9.})
 with pytest.raises(ValueError,match='source/scope'):removal_followup_view(i,d)

def test_optional_absent():assert removal_followup_view({},[]) is None
