from pathlib import Path
from copy import deepcopy
import json,gzip
import pytest
from canonical_json import digest
from st_huke_date_proof import apply_huke_date_proof

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/huke-date-proof.json.gz').read_bytes()))
def view(i):
 old=next(e for e in i['test_reading']['verified_events']if e['id']=='pre_rule_boundary_600608')
 return apply_huke_date_proof(i,i['test_reading'],lambda e:old['alternate_observation'])
def seal(i):
 p=i['huke_date_proof'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_official_day_changes_source_identity_not_effective_date_or_first_publication_claim():
 i=fixture();before=deepcopy(i);v,reading=view(i);assert i==before
 assert v['effective_on']==v['formal_published_on']=='2026-06-08' and v['legacy_path_date']=='2026-06-07'
 assert v['legacy_catalog_role']=='earlier_arrangement_notice'and not v['earliest_publication_certified']
 assert v['historical_record']['published_on']=='2026-06-07'and v['current_record']['published_on']=='2026-06-08'
 assert 'selected_pages'not in v['current_record']['source']and 'alternate_observation'not in v['current_record']
 assert(reading['verified_documents'],reading['raw_fact_records'],reading['deduplicated_event_count'])==(216,209,208)
 assert v['new_facts']==v['new_unique_documents']==2 and v['method_promotions']==0
 new=[e for e in reading['verified_events']if e['id'].startswith('huke_')];assert len(new)==2 and len({e['observation_key']for e in new})==1
 assert all(e['same_company_day_facts']==2 for e in new)
@pytest.mark.parametrize('bad',['digest','through','utc_day','time_value','same_document','legacy_title','legacy_id','first_publication','count','same_bytes','stage','page','promotion'])
def test_source_date_or_stage_overclaims_rejected(bad):
 i=fixture();p=i['huke_date_proof'];s=next(s for s in p['sources']if s['announcement_id']=='1225356346')
 if bad=='digest':p['content_digest']='bad'
 elif bad=='through':i['through']='2026-11-05'
 elif bad=='utc_day':s['published_on']='2026-06-07'
 elif bad=='time_value':s['metadata']['announcementTime']+=86400000
 elif bad=='same_document':p['legacy_catalog_role']='same_firstday_notice'
 elif bad=='legacy_title':p['legacy_catalog_title']='首日提示'
 elif bad=='legacy_id':p['legacy_catalog_id']='changed'
 elif bad=='first_publication':p['earliest_publication_certified']=True
 elif bad=='count':p['events'].pop()
 elif bad=='same_bytes':s['sha256']='different'
 elif bad=='stage':s['selected_pages']['1']=s['selected_pages']['1'].replace('2026-046','2026-045')
 elif bad=='page':s['selected_pages']['1']='changed'
 elif bad=='promotion':p['method_promotions']=1
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)
def test_new_window_must_equal_previously_computed_same_date_alternative():
 i=fixture();old=next(e for e in i['test_reading']['verified_events']if e['id']=='pre_rule_boundary_600608')
 with pytest.raises(ValueError):apply_huke_date_proof(i,i['test_reading'],lambda e:old['observation'])
def test_missing_packet_preserves_reading():
 reading={'a':1};assert apply_huke_date_proof({},reading,lambda e:e)==(None,reading)
