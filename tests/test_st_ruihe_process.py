from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json,gzip
import pytest
from canonical_json import digest
from st_ruihe_process import ruihe_process
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-ruihe-process.json.gz').read_bytes()))
def seal(i):
 p=i['ruihe_process'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def view(i):return ruihe_process(i,i['test_reading'],i['test_initial'],lambda e:event_context(e,e['symbol'],i,i['test_daily']))
def test_partial_payment_clocks_and_promise_do_not_certify_full_execution():
 i=fixture();old=deepcopy(i);v,r=view(i);assert i==old
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['verified_companies'])==(236,229,228,95)
 assert v['funding']['industry_reported_deposit_yuan']=='50000000'and v['funding']['planned_total_yuan']=='1873200000.00'and not v['funding']['full_investment_paid_verified']
 assert v['funding']['remaining_payment_trigger']=='manager_written_payment_notice'and v['commitment']['lock_start']=='actual_share_transfer_to_investor_account'
 assert v['new_files']==4 and v['new_pages']==36 and v['selected_source_pages']==18
 assert r['supplement']['unique_company_days']==212 and {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 assert [r['agency']for r in v['investigation_comparison']]==['公安机关','中国证监会','中国证监会']
 assert '口头沟通' in v['investigation_comparison'][0]['evidence_level']and not v['q3']['audited']
@pytest.mark.parametrize('bad',['digest','scope','prior','source','page','metadata','deposit','total','clock','paid','accepted','approved','transfer','lock_start','own_money','ratio','investor','finance_paid','financial_sign','audit','document_date','comparator','private_page','promotion'])
def test_no_unsupported_payment_stage_or_agency_and_no_irrelevant_profile_pages(bad):
 i=fixture();p=i['ruihe_process'];s=next(s for s in p['sources']if s['announcement_id']=='1225307829')
 if bad=='digest':p['content_digest']='bad'
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='prior':i['test_reading']['verified_events'].pop()
 elif bad=='source':p['sources'].pop()
 elif bad=='page':s['selected_pages']['11']='changed'
 elif bad=='metadata':s['metadata']['announcementTime']+=86400000
 elif bad=='deposit':p['funding']['industry_reported_deposit_yuan']='76500000'
 elif bad=='total':p['funding']['planned_total_yuan']='951234375.00'
 elif bad=='clock':p['funding']['remaining_payment_trigger']='signature_date'
 elif bad=='paid':p['funding']['full_investment_paid_verified']=True
 elif bad=='accepted':p['funding']['court_acceptance_verified']=True
 elif bad=='approved':p['funding']['plan_approval_verified']=True
 elif bad=='transfer':p['funding']['share_transfer_verified']=True
 elif bad=='lock_start':p['commitment']['lock_start']='promise_date'
 elif bad=='own_money':p['commitment']['own_funds_received_verified']=True
 elif bad=='ratio':p['commitment']['subject']='all_investors'
 elif bad=='investor':p['investors'].pop()
 elif bad=='finance_paid':p['funding']['finance_deposits_paid_verified']=True
 elif bad=='financial_sign':p['q3']['parent_equity']='121614589.16'
 elif bad=='audit':p['q3']['audited']=True
 elif bad=='document_date':p['rows'][0]['document_dated_on']='2026-05-13'
 elif bad=='comparator':next(s for s in i['initial_status_coverage']['sources']if s['announcement_id']=='1225405413')['selected_pages']['1']='公安机关'
 elif bad=='private_page':s['selected_pages']['9']='unneeded identity';s['page_hashes'][8]=sha256(b'unneeded identity').hexdigest()
 elif bad=='promotion':p['method_promotions']=1
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError,StopIteration)):view(i)
def test_late_observations_keep_unfinished_twenty_day_windows_null():
 v,_=view(fixture());r=next(r for r in v['rows']if r['change_kind']=='commitment_strengthened');assert r['observation']['windows']['5']['through']=='2026-11-06'and r['observation']['windows']['20']['stock_pct']is None

def test_no_packet_preserves_current_reading():assert ruihe_process({}, {'old':1},None,lambda e:e)==(None,{'old':1})
