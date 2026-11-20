from copy import deepcopy
from st_evidence_inventory import audit_source_inputs,evidence_inventory

def doc(a='1',h='a',pages=None):return {'announcement_id':a,'sha256':h*64,'pages':2,'symbol':'000001',**({'selected_pages':pages}if pages is not None else{})}
def test_identity_deduplication_is_not_reference_or_reading_count():
 source=doc(pages={'1':'some text'});inputs={'source':source,'repeat':deepcopy(source),'metadata':doc('2')};before=deepcopy(inputs);r=audit_source_inputs(inputs,'frozen');c=r['counts'];assert inputs==before
 assert c['embedded_reference_records']==3 and c['unique_id_sha_pairs']==2 and c['with_retained_extracted_text']==1 and c['metadata_or_reference_only']==1
 assert c['retained_nonempty_page_positions']==1 and c['with_all_declared_page_positions_nonempty']==0

def test_distinct_files_same_id_are_not_silently_merged():
 r=audit_source_inputs({'one':doc(),'two':doc(h='b')},'frozen');assert r['counts']['unique_id_sha_pairs']==2 and r['counts']['ids_with_multiple_sha']==1

def test_glyph_versions_preserved_instead_of_automatically_rewriting_dates():
 r=audit_source_inputs({'one':doc(pages={'1':'二〇二六'}),'two':doc(pages={'1':'二◯二六'})},'frozen');assert r['counts']['unique_id_sha_pairs']==1 and r['counts']['documents_with_multiple_normalized_page_variants']==1

def test_all_nonempty_positions_do_not_become_read_certification():
 r=audit_source_inputs({'one':doc(pages={'1':'excerpt','2':'excerpt'})},'frozen');assert r['counts']['with_all_declared_page_positions_nonempty']==1 and r['counts']['not_full_read_certifications']is True

def test_inventory_missing_packet_does_not_change_old_snapshots():assert evidence_inventory({})is None

def test_packet_excludes_itself_and_rejects_changed_evidence(monkeypatch):
 import pytest
 import st_evidence_inventory as module
 from canonical_json import digest
 baseline={'source':doc(pages={'1':'retained'})}
 calculation=audit_source_inputs(baseline,'snapshot')
 view={'counts':calculation['counts']}
 for key,value in {'BASELINE_DIGEST':digest(baseline),'SOURCE_SNAPSHOT':'snapshot','INVENTORY_DIGEST':digest(calculation),'VIEW_DIGEST':digest(view)}.items():monkeypatch.setattr(module,key,value)
 packet={'version':1,'calculation':calculation,'result':view}
 packet['content_digest']=digest(packet)
 inputs={**baseline,'evidence_inventory':packet}
 result=evidence_inventory(inputs)
 assert result['counts']['embedded_reference_records']==1
 result['counts']['embedded_reference_records']=99
 assert evidence_inventory(inputs)['counts']['embedded_reference_records']==1
 changed=deepcopy(inputs);changed['source']['selected_pages']['1']='different'
 with pytest.raises(ValueError,match='baseline changed'):evidence_inventory(changed)
 changed=deepcopy(inputs);changed['evidence_inventory']['result']['counts']['unique_id_sha_pairs']=900
 changed['evidence_inventory']['content_digest']=digest({k:v for k,v in changed['evidence_inventory'].items()if k!='content_digest'})
 with pytest.raises(ValueError,match='evidence changed'):evidence_inventory(changed)
