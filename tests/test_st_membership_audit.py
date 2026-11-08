import json
from hashlib import sha256
from copy import deepcopy
import pytest
from canonical_json import digest
from st_membership_audit import membership_audit_view,scope_digest

def source(venue,data):
 raw=json.dumps(data,ensure_ascii=False);return {'venue':venue,'raw_json':raw,'sha256':sha256(raw.encode()).hexdigest(),'url':'https://example.test/list','observed_at':'2026-11-09T01:00:00+00:00'}
def sz(page,rows,date='2026-11-06'):
 return source('SZ',[{'metadata':{'catalogid':'fxjsb','tabkey':'tab1','name':'风险警示股票','subname':date,'pageno':page,'pagecount':2,'recordcount':3},'data':[{'zqdm':c,'gsjc':f'<a><u>{n}</u></a>'} for c,n in rows],'error':None}])
def fixture():
 i={'through':'2026-11-06','members':[{'symbol':c,'name':n,'trade_date':d,'ts_code':c+'.'+v} for d in ('2026-07-03','2026-11-06') for c,n,v in [('000001','ST甲','SZ'),('002001','*ST乙','SZ'),('600001','ST丙','SH')]]}
 sources=[sz(1,[('000001','ST甲'),('300001','ST创业')]),sz(2,[('002001','*ST乙')]),source('SH',{'sqlId':'PL_SSGSXX_FXJSBGPLB','queryDate':'','pageHelp':{'total':2},'result':[{'INSTRUMENT_ID':'600001','INSTRUMENT_SHORT':'ST丙'},{'INSTRUMENT_ID':'900001','INSTRUMENT_SHORT':'ST丙B'}]})]
 p={'target_dates':['2026-07-03','2026-11-06'],'scope_digest':scope_digest(i),'list_sources':sources,'official_scope_sources':[]};i['official_membership_audit']=p;reseal(i);return i

def reseal(i):
 p=i['official_membership_audit'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})

def test_dated_complete_pages_only_verify_own_date_and_main_a():
 x=membership_audit_view(fixture());assert x['targets']==[{'date':'2026-07-03','provider_count':3,'directly_verified_count':0,'not_directly_verified_count':3},{'date':'2026-11-06','provider_count':3,'directly_verified_count':2,'not_directly_verified_count':1}];assert x['venues'][0]['excluded_count']==1;assert x['venues'][1]['status']=='undated_observation' and x['venues'][1]['same_codes_and_names'];assert x['venues'][1]['excluded_rows']==[{'symbol':'900001','name':'ST丙B'}]

def test_matching_codes_cannot_replace_unknown_date_or_server_observation_time():
 i=fixture();p=i['official_membership_audit'];p['list_sources'][2]['observed_at']='2026-11-06';reseal(i);x=membership_audit_view(i);assert x['venues'][1]['as_of'] is None and x['targets'][1]['directly_verified_count']==2

def test_partial_pages_and_repeated_codes_fail_closed():
 i=fixture();i['official_membership_audit']['list_sources'].pop(1);reseal(i)
 with pytest.raises(ValueError,match='pages incomplete'):membership_audit_view(i)
 i=fixture();i['official_membership_audit']['list_sources'][1]=sz(2,[('000001','ST甲')]);reseal(i)
 with pytest.raises(ValueError,match='duplicate'):membership_audit_view(i)

def test_date_drift_raw_tampering_and_scope_fail_closed():
 i=fixture();i['official_membership_audit']['list_sources'][1]=sz(2,[('002001','*ST乙')],date='2026-11-05');reseal(i)
 with pytest.raises(ValueError,match='metadata drift'):membership_audit_view(i)
 i=fixture();i['official_membership_audit']['list_sources'][0]['raw_json']+=' ';reseal(i)
 with pytest.raises(ValueError,match='raw source'):membership_audit_view(i)
 i=fixture();i['members'][0]['name']='changed'
 with pytest.raises(ValueError,match='binding'):membership_audit_view(i)

def test_conflicting_code_or_name_is_exposed_not_certified():
 i=fixture();i['official_membership_audit']['list_sources'][1]=sz(2,[('002001','ST乙')]);reseal(i);x=membership_audit_view(i);assert x['venues'][0]['status']=='dated_conflict';assert x['venues'][0]['name_differences']==[{'symbol':'002001','official':'ST乙','provider':'*ST乙'}];assert x['targets'][1]['directly_verified_count']==0

def test_optional_for_old_callers():assert membership_audit_view({}) is None

def anchor_fixture():
 i=fixture();i['calendar']=['2026-07-03'];i['fixed_prices']=[]
 c={'symbol':'600001','name':'ST丙','anchor':'2026-07-03','status_disclosed_on':'2026-07-03','scope_digest':digest({k:i[k] for k in ('calendar','through','fixed_prices','members')}),'released_accounts':[{'amount_yuan':'1.01'},{'amount_yuan':'2.02'}],'released_total_yuan':'3.03','facts':[{'published_on':'2026-07-03','document_dated_on':'2026-07-02','source':{'sha256':'source','url':'https://example.test','page':1,'title':'issuer'}}]};i['official_membership_audit']['issuer_checks']=[c];reseal(i);return i

def test_issuer_anchor_evidence_does_not_certify_full_list_or_mutate_source():
 i=anchor_fixture();x=membership_audit_view(i);assert x['issuer_checks'][0]['name']=='ST丙';assert x['targets'][0]['directly_verified_count']==0;x['issuer_checks'][0]['events']=[];assert 'events' not in i['official_membership_audit']['issuer_checks'][0]

def test_issuer_anchor_rejects_amount_name_date_and_scope_conflicts():
 for field,value,match in [('released_total_yuan','3.04','total'),('name','*ST丙','name'),('status_disclosed_on','2026-07-04','anchor'),('scope_digest','changed','scope')]:
  i=anchor_fixture();i['official_membership_audit']['issuer_checks'][0][field]=value;reseal(i)
  with pytest.raises(ValueError,match=match):membership_audit_view(i)
 i=anchor_fixture();i['official_membership_audit']['issuer_checks'][0]['facts'][0]['published_on']='2026-07-04';reseal(i)
 with pytest.raises(ValueError,match='timely'):membership_audit_view(i)
