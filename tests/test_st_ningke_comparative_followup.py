from pathlib import Path
from copy import deepcopy
import json,gzip
import pytest
from canonical_json import digest
from st_ningke_comparative_followup import ningke_comparative_followup

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-ningke-comparative-followup.json.gz').read_bytes()))
def test_visual_corroboration_does_not_silently_amend_original_report():
 d=fixture();before=deepcopy(d);r=ningke_comparative_followup(d,d['test_prior']);assert d==before
 assert r['annual_h1_balance_q3_agree']and not r['h1_summary_conflict_resolved']and not r['simple_2024_year_shift_supported']
 assert r['comparison_rows'][1]['change_using_corroborated_balance']=='-132468807.22'
 assert r['annual_scan_reading']['basis']=='human_visual_transcription'and not r['annual_scan_reading']['automatic_text_match']
 assert r['annual_scan_reading']['pdf_pages']==[7,8]and r['method_promotions']==0
 r['comparison_rows'].clear();assert len(ningke_comparative_followup(d,d['test_prior'])['comparison_rows'])==2
 assert ningke_comparative_followup({},None)is None
@pytest.mark.parametrize('kind',['annual_source','h1_source','prior','year','closed','visual'])
def test_resealed_changes_cannot_change_period_or_claim_resolution(kind):
 d=fixture();p=d['ningke_comparative_followup']
 if kind=='annual_source':next(s for s in d['initial_fourteenth_four']['sources']if s['announcement_id']=='1225172303')['sha256']='bad'
 elif kind=='h1_source':next(s for s in d['fourteenth_period_followup']['sources']if s['announcement_id']=='1225530042')['selected_pages']['6']='bad'
 elif kind=='prior':d['test_prior'].clear()
 elif kind=='year':p['result']['values']['annual_2024']['parent_equity']='-99206789.77'
 elif kind=='closed':p['result']['h1_summary_conflict_resolved']=True
 else:p['result']['annual_scan_reading']['automatic_text_match']=True
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):ningke_comparative_followup(d,d['test_prior'])
