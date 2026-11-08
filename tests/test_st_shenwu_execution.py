import json
from pathlib import Path
import pytest
from canonical_json import digest
from st_shenwu_execution import shenwu_execution_view,scope_digest

def fixture():
 i=json.loads((Path(__file__).parent/'fixtures/shenwu-execution.json').read_text());i['shenwu_execution']['scope_digest']=scope_digest(i);seal(i);return i
def seal(i):
 p=i['shenwu_execution'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_completed_share_registration_is_not_issuer_cash_or_fulfilled_compensation():
 v=shenwu_execution_view(fixture());t=v['transfer'];assert t['status']=='registration_complete_per_disclosures' and t['reported_change_on']=='2026-10-08'
 assert t['issuer_cash_received_yuan']is None and t['compensation_fulfilled']is None and t['exact_registry_receipt_on']is None
 assert v['independent_company_count']==1 and len(v['event_ids'])==4 and len([s for s in v['sources']if not s.get('reused')])==6
 assert v['date_conflict']['quoted_cross_reference_date']=='2025-07-07' and v['date_conflict']['first_primary_publication']=='2026-07-07'
def test_share_denominators_and_consortium_total_are_not_swapped_with_current_holdings_or_revenue():
 v=shenwu_execution_view(fixture());assert v['ratios']['historical_pct_of_original']=='79.22' and v['ratios']['auction_pct_of_then_holdings']=='45.45'
 assert v['contract_components_total_yuan']=='717120000.00' and v['contract']['allocated_to_subsidiary_yuan']is None
 assert v['contract']['recognized_revenue_yuan']is None and v['contract']['actual_start_on']is None
@pytest.mark.parametrize('mutation',['receipt','compensation','effective','allocation','component','denominator','date','source','known','receivable','scope'])
def test_claims_need_correct_subject_source_stage_date_and_arithmetic(mutation):
 i=fixture();p=i['shenwu_execution']
 if mutation=='receipt':p['transfer']['issuer_cash_received_yuan']='100'
 if mutation=='compensation':p['transfer']['compensation_fulfilled']=True
 if mutation=='effective':p['contract']['exact_effective_on']='2026-10-26'
 if mutation=='allocation':p['contract']['scope']='issuer_total'
 if mutation=='component':p['contract']['components_yuan']['design']='3200000.00'
 if mutation=='denominator':p['transfer']['original_reorganization_shares']='72600000'
 if mutation=='date':p['transfer']['issuer_signed_on']='2026-10-13'
 if mutation=='source':p['transfer']['report_date_sources'][0]['page_text_hash']='0'*64
 if mutation=='known':p['contract']['published_on']='2026-10-26'
 if mutation=='receivable':p['receivable']['latest_after_report_status']='still_unpaid'
 if mutation=='scope':i['fixed_prices']=[{'changed':True}]
 seal(i)
 with pytest.raises(ValueError):shenwu_execution_view(i)
def test_old_snapshot_without_packet_is_not_invented():assert shenwu_execution_view({})is None
