from pathlib import Path
from copy import deepcopy
import json,gzip
import pytest
from canonical_json import digest
from st_warning_basis_followup import warning_basis_followup
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-warning-basis-followup.json.gz').read_bytes()))
def seal(i):
 p=i['warning_basis_followup'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def view(i):return warning_basis_followup(i,i['test_reading'],i['test_initial'],i['test_membership'],lambda e:event_context(e,e['symbol'],i,i['test_daily']))
def test_basis_closed_but_settlement_does_not_remove_all_risk_or_certify_membership():
 i=fixture();old=deepcopy(i);v,r=view(i);assert i==old
 assert v['new_files']==10 and v['new_pages']==32 and v['resolved_basis_symbols']==['002305','000639']
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['verified_companies'])==(232,225,224,95)
 assert {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 assert v['settlement']['assets_yuan']=='68000000'and v['settlement']['cash_principal_yuan']=='62000000'and not v['settlement']['all_principal_cash']
 assert v['nanzhi_q3']['operating_cash']=='-28863316.49'and not v['nanzhi_q3']['audited']
 assert v['nanzhi_endpoint']['official_name']=='*ST南置'and not v['full_membership_certification_added']and v['method_promotions']==0
 events=[e for e in v['rows']if e['matter_id']=='xiwang_occupation'];assert len(events)==3 and sum(e['change_kind']=='occupation_settled'for e in events)==1
 assert i['test_initial']['counts']['timely_reading_after']==20
 assert r['supplement']['unique_company_days']==len({(e['symbol'],e['published_on'])for e in r['verified_events']})==208
 assert v['historical_company_day_counter']==192
@pytest.mark.parametrize('bad',['digest','scope','reading','initial','source_missing','metadata_day','page','catalog','all_cash','cash_amount','cash_flags','audited','cash_row','quarter_unit','official_date','official_name','event_day','document_date','repeat_settlement','promotion'])
def test_unsupported_dates_payments_status_and_accounting_mappings_rejected(bad):
 i=fixture();p=i['warning_basis_followup'];s=p['sources'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='reading':i['test_reading']['verified_events'].pop()
 elif bad=='initial':i['test_initial']['counts']['timely_reading_after']=21
 elif bad=='source_missing':p['sources'].pop()
 elif bad=='metadata_day':next(x for x in p['sources']if x['metadata'])['metadata']['announcementTime']+=86400000
 elif bad=='page':s['selected_pages']['1']='changed'
 elif bad=='catalog':i['announcement_study']['catalogs'][s['symbol']]['rows'][0]['url']='https://invalid.example/a.PDF'
 elif bad=='all_cash':p['settlement']['all_principal_cash']=True
 elif bad=='cash_amount':p['settlement']['cash_principal_yuan']='130000000'
 elif bad=='cash_flags':p['settlement']['assets_delivered']=False
 elif bad=='audited':p['nanzhi_q3']['audited']=True
 elif bad=='cash_row':p['nanzhi_q3']['operating_cash']=p['nanzhi_q3']['parent_profit']
 elif bad=='quarter_unit':p['nanzhi_q3']['unit']='wan_yuan'
 elif bad=='official_date':i['test_membership']['venues'][0]['as_of']='2026-11-05'
 elif bad=='official_name':i['test_membership']['venues'][0]['rows'][0]['name']='南国置业'
 elif bad=='event_day':p['rows'][0]['published_on']='2026-07-03'
 elif bad=='document_date':p['rows'][0]['document_dated_on']='2025-04-28'
 elif bad=='repeat_settlement':next(x for x in p['rows']if x['change_kind']=='remaining_risk_reaffirmed')['change_kind']='occupation_settled'
 elif bad=='promotion':p['method_promotions']=1
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError,StopIteration)):view(i)
def test_background_and_incomplete_windows_remain_null_not_filled_with_zero():
 v,_=view(fixture());old=next(r for r in v['rows']if r['source']['announcement_id']=='1223381687');late=next(r for r in v['rows']if r['source']['announcement_id']=='1225646118')
 assert old['observation']['anchor']is None and all(x['stock_pct']is None for x in old['observation']['windows'].values())
 assert late['observation']['windows']['20']['stock_pct']is None and late['observation']['windows']['5']['through']=='2026-11-06'
def test_no_packet_preserves_prior_reading():assert warning_basis_followup({}, {'old':1},None,None,lambda e:e)==(None,{'old':1})
