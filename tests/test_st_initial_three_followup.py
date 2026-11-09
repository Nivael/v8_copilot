from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json,gzip
import pytest
from canonical_json import digest
from st_initial_three_followup import initial_three_followup
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-three-followup.json.gz').read_bytes()))
def seal(i):
 p=i['initial_three_followup'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def view(i):return initial_three_followup(i,i['test_reading'],i['test_initial'],lambda e:event_context(e,e['symbol'],i,i['test_daily']))
def test_updates_keep_old_facts_and_distinguish_approval_subjects_and_payment():
 i=fixture();before=deepcopy(i);v,r=view(i);assert i==before
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['verified_companies'])==(251,244,243,95)
 assert {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 assert v['new_files']==15 and v['new_pages']==127 and v['company_day_groups']==14 and v['reading_company_days']==226
 assert v['claims']['shuyuan_penalty_stage']=='prior_notice_not_final'
 assert not v['claims']['chunxing_full_funding_verified']and not v['claims']['zhongyan_court_acceptance_verified']and not v['claims']['shareholder_debt_waived']
 assert v['claims']['subsidiary_application_result']=='court_permitted_withdrawal_not_entered_liquidation'
 assert [q['operating_cash'].startswith('-')for q in v['financials']]==[False,False,True]
 same=[e for e in v['rows']if e['symbol']=='000909'and e['published_on']=='2026-09-10'];assert len(same)==2 and same[0]['observation']==same[1]['observation']and all(e['same_company_day_facts']==2 for e in same)
@pytest.mark.parametrize('bad',['digest','scope','parent','duplicate_source','missing_source','page_hash','catalog','issuer','source_day','stage','entity','evidence_page','final_penalty','fine_paid','warning_band','deposit','payment_clock','full_paid','court_accepted','subsidiary','debt_waiver','all_ceiling_paid','quarter_sign','quarter_period','audited','private_page','method','membership'])
def test_unsupported_stage_subject_or_financial_change_is_rejected(bad):
 i=fixture();p=i['initial_three_followup'];s=next(s for s in p['sources']if s['announcement_id']=='1225607502')
 if bad=='digest':p['content_digest']='bad'
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='parent':i['test_reading']['verified_events'].pop()
 elif bad=='duplicate_source':p['sources'].append(s)
 elif bad=='missing_source':p['sources'].pop()
 elif bad=='page_hash':s['selected_pages']['17']='changed'
 elif bad=='catalog':s['url']='https://example.invalid/wrong.pdf'
 elif bad=='issuer':s['symbol']='000909'
 elif bad=='source_day':s['announcement_date']='2026-10-15'
 elif bad=='stage':p['rows'][0]['change_kind']='final_penalty'
 elif bad=='entity':next(r for r in p['rows']if r['change_kind']=='subsidiary_application_withdrawn')['entity_scope']='issuer'
 elif bad=='evidence_page':p['rows'][0]['evidence_pages']=[99]
 elif bad=='final_penalty':p['claims']['shuyuan_penalty_stage']='final'
 elif bad=='fine_paid':p['claims']['shuyuan_fine_paid']=True
 elif bad=='warning_band':p['claims']['shuyuan_band_pct']=5
 elif bad=='deposit':p['claims']['chunxing_reported_registration_deposit_yuan']='47355000'
 elif bad=='payment_clock':p['claims']['chunxing_remainder_trigger']='signature'
 elif bad=='full_paid':p['claims']['chunxing_full_funding_verified']=True
 elif bad=='court_accepted':p['claims']['zhongyan_court_acceptance_verified']=True
 elif bad=='subsidiary':p['claims']['zhongyan_subsidiary']='中化岩土'
 elif bad=='debt_waiver':p['claims']['shareholder_debt_waived']=True
 elif bad=='all_ceiling_paid':p['claims']['shareholder_ceiling_all_paid_verified']=True
 elif bad=='quarter_sign':p['financials'][2]['operating_cash']='110017404.08'
 elif bad=='quarter_period':p['financials'][0]['period_start']='2026-07-01'
 elif bad=='audited':p['financials'][0]['audited']=True
 elif bad=='private_page':s['selected_pages']['4']='unneeded investor profile';s['page_hashes'][3]=sha256(b'unneeded investor profile').hexdigest()
 elif bad=='method':p['method_promotions']=1
 elif bad=='membership':p['full_membership_certification_added']=True
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)
def test_late_shareholder_approval_windows_remain_null_without_filling_zero():
 v,_=view(fixture());r=next(r for r in v['rows']if r['change_kind']=='shareholder_contract_approval');assert r['observation']['windows']['5']['through']is None and r['observation']['windows']['20']['stock_pct']is None

def test_absent_packet_leaves_legacy_reading_unchanged():assert initial_three_followup({}, {'old':1},None,lambda e:e)==(None,{'old':1})
