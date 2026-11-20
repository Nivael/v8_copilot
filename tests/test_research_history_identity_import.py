from copy import deepcopy
import json,sqlite3
import pytest
from canonical_json import digest
from research_history import import_ledger,import_ledger_with_audit,deduplicate
from research_identity_notes import publish_notes,note_path,bind_study_identity
from research_repository import ResearchRunCreate
from test_research_identity_notes import sample


def test_corrected_identity_is_quarantined_without_rewriting_or_inventing_original_question(tmp_path):
 ledger,pack,note,scope,raw=sample(tmp_path)
 publish_notes([note],ledger_db=ledger.path,scopes_path=scope)
 records,audit=import_ledger_with_audit(ledger.path,{'002717.SZ':'岭南','603838.SH':'四通'},scopes_path=scope)
 assert records==[] and audit['ledger_rows']==1 and audit['imported_rows']==0
 assert audit['identity_availability']=='available'
 assert audit['quarantined_runs']==[{'run_id':raw['run_id'],'run_digest':digest(raw),'reason':'corrected_research_identity_not_original_question'}]
 assert import_ledger(ledger.path,{},scopes_path=scope)==[]
 with sqlite3.connect(ledger.path)as db:
  db.row_factory=sqlite3.Row;assert dict(db.execute('select * from research_runs').fetchone())==raw


def test_unreviewed_rows_remain_saved_research_with_explicit_audit_boundary(tmp_path):
 ledger,pack,note,scope,raw=sample(tmp_path)
 with pytest.raises(ValueError,match='corrections are missing'):import_ledger(ledger.path,{},scopes_path=scope)
 records,audit=import_ledger_with_audit(ledger.path,{'002717.SZ':'岭南'},scopes_path=scope,allow_unreviewed=True)
 assert audit['identity_availability']=='missing' and audit['unreviewed_rows']==1
 assert records[0]['kind']=='saved_research' and records[0]['date_source']=='saved_research_time_not_original_ask'
 assert records[0]['question']==raw['question_text']
 publish_notes([note],ledger_db=ledger.path,scopes_path=scope)
 bound=bind_study_identity(pack,question='另一条真实研究登记',object_refs=['002717'],as_of=note['corrected_research_as_of'])
 ledger.store_evidence_pack(bound.model_dump(mode='json'))
 other=ledger.record(ResearchRunCreate(request_id=bound.query_plan_id,question_text='另一条真实研究登记',normalized_intent='research_question',object_refs=['002717'],evidence_pack_ids=[bound.pack_id],final_answer='保留原回答',validation_report={'valid':True},source_freshness=bound.source_freshness,agent_surface='test'))
 records,audit=import_ledger_with_audit(ledger.path,{},scopes_path=scope)
 assert [r['id']for r in records]==[other.run_id] and audit['unreviewed_rows']==1


@pytest.mark.parametrize('target',['notes','run','scope'])
def test_invalid_identity_binding_stops_import_instead_of_falling_back_to_raw(tmp_path,target):
 ledger,pack,note,scope,raw=sample(tmp_path)
 publish_notes([note],ledger_db=ledger.path,scopes_path=scope)
 if target=='notes':note_path(ledger.path).write_text('{broken')
 elif target=='scope':scope.write_text('{broken')
 else:
  with sqlite3.connect(ledger.path)as db:db.execute("update research_runs set final_answer='tampered'")
 with pytest.raises(ValueError,match='identity corrections are invalid'):import_ledger(ledger.path,{},scopes_path=scope)


def test_same_wording_saved_studies_keep_distinct_run_identities():
 a={'id':'first','asked_at':'2026-06-01T01:00:00Z','question':'相同题目','kind':'saved_research','answers':[{'text':'旧判断'}],'sources':[]}
 b={**deepcopy(a),'id':'second','answers':[{'text':'后续判断'}]}
 rows=deduplicate([a,b]);assert len(rows)==2 and {r['id']for r in rows}=={'first','second'}
 assert rows[0]['answers']!=rows[1]['answers']


@pytest.mark.parametrize('binding',['id','source','occurrence'])
def test_prepared_import_cannot_reintroduce_quarantined_run_even_after_merge_or_relabel(tmp_path,binding):
 from research_history import validate_saved_history_identities,publish
 ledger,pack,note,scope,raw=sample(tmp_path)
 publish_notes([note],ledger_db=ledger.path,scopes_path=scope)
 r={'id':raw['run_id'] if binding=='id'else 'merged-record','kind':'saved_research','sources':[]}
 if binding=='source':r.update(kind='original_question',sources=[{'kind':'research_ledger','run_id':raw['run_id']}])
 if binding=='occurrence':r.update(kind='original_question',occurrences=[{'id':raw['run_id']}])
 with pytest.raises(ValueError,match='quarantined saved research'):validate_saved_history_identities([r],ledger_db=ledger.path,scopes_path=scope)
 # Gate runs before reading prices or writing any history file.
 with pytest.raises(ValueError,match='quarantined saved research'):publish({'records':[r],'sources':[]},root=tmp_path/'new-history',ledger_db=ledger.path,identity_scopes_path=scope)
 assert not (tmp_path/'new-history').exists()


def test_prepared_saved_import_requires_registry_but_original_messages_do_not(tmp_path):
 from research_history import validate_saved_history_identities
 ledger,pack,note,scope,raw=sample(tmp_path)
 validate_saved_history_identities([{'id':'QUESTION-real','kind':'original_question','sources':[{'kind':'chatgpt'}]}],ledger_db=ledger.path)
 with pytest.raises(ValueError,match='registry unavailable'):validate_saved_history_identities([{'id':raw['run_id'],'kind':'saved_research','sources':[]}],ledger_db=ledger.path)
