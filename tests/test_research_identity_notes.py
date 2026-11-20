from copy import deepcopy
from datetime import datetime,timezone
import json,sqlite3
import pytest
import research_identity_notes as n
from canonical_json import digest
from evidence_gateway import EvidencePack
from research_repository import ResearchRunCreate,ResearchRunLedger
from case_research_scopes import mark_historical_review

def source_pack():
 payload={'contract_version':'v8_evidence_pack_v2','question_scope':{'question':'旧登记岭南','object':{'kind':'stock','ref':'002717'},'intent':'research_question','as_of':'2026-05-26'},'query_plan_id':'old-plan','rows':[{'row_id':'new-study','result':'四通窗口'}],'lens_invocations':[{'release_id':'old-lens'}],'freshness_manifest':{'as_of':'2026-05-26'},'source_freshness':{'old':'2026-05-26'},'provenance':['saved-source'],'coverage_gaps':[],'definitions':[],'allowed_claims':[],'forbidden_inferences':[],'validation_catalog':{},'applicable_experiences':[{'experience_id':'EXP-OLD','title':'旧检索','experience_type':'method','value_summary':'背景','trigger_conditions':[],'topic_tags':[],'answer_rubric':[],'coverage_boundaries':[],'version':1,'not_evidence':True}],'deterministic_response':{'request_id':'old-request'}}
 h=digest(EvidencePack.model_construct(**payload).model_dump(mode='json',exclude={'pack_id','pack_digest'}))
 return EvidencePack.model_validate({**payload,'pack_id':'EP-'+h[:20].upper(),'pack_digest':h})

def sample(tmp_path):
 ledger=ResearchRunLedger(tmp_path/'runs.sqlite3');pack=source_pack();ledger.store_evidence_pack(pack.model_dump(mode='json'));r=ledger.record(ResearchRunCreate(request_id='old-request',question_text='旧登记岭南',normalized_intent='research_question',object_refs=['002717'],evidence_pack_ids=[pack.pack_id],final_answer='实际复盘四通窗口',validation_report={'valid':True},source_freshness={},agent_surface='test'))
 mark_historical_review(r.run_id,'四通窗口核对',ledger_db=ledger.path,directory=tmp_path/'scopes')
 with sqlite3.connect(ledger.path)as db:
  db.row_factory=sqlite3.Row;raw=dict(db.execute('select * from research_runs').fetchone())
 e={'run_id':r.run_id,'run_digest':digest(raw),'original_pack_id':pack.pack_id,'original_scope_digest':digest(pack.question_scope),'corrected_question':'核四通窗口','corrected_object_refs':['603838'],'corrected_research_as_of':datetime.now(timezone.utc).date().isoformat(),'purpose_basis':'四通窗口核对','reviewed_at':datetime.now(timezone.utc).isoformat(),'experience_context':'inherited_unreviewed','topic_changed':True,'original_request_id':'old-request'}
 return ledger,pack,e,tmp_path/'scopes/current.json',raw

def test_reading_correction_preserves_original_run_and_pack(tmp_path):
 ledger,pack,e,scope,raw=sample(tmp_path);v=n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope);view=n.reading_view(ledger_db=ledger.path,scopes_path=scope);assert view['availability']=='available';assert view['corrections'][0]['corrected_question']=='核四通窗口';assert view['corrections'][0]['original_question']=='旧登记岭南'
 with sqlite3.connect(ledger.path)as db:
  db.row_factory=sqlite3.Row;assert dict(db.execute('select * from research_runs').fetchone())==raw
  assert json.loads(db.execute('select payload_json from evidence_packs').fetchone()[0])==pack.model_dump(mode='json')
 assert (n.note_path(ledger.path).parent/'history'/(v['content_digest']+'.json')).exists()
 with pytest.raises(ValueError,match='append-only'):n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope)

@pytest.mark.parametrize('target',['run','scope','purpose'])
def test_binding_changes_reject_even_resealed_notes(tmp_path,target):
 ledger,pack,e,scope,raw=sample(tmp_path);n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope)
 if target=='run':
  with sqlite3.connect(ledger.path)as db:db.execute("update research_runs set final_answer='changed'")
 elif target=='scope':
  payload=pack.model_dump(mode='json');payload['question_scope']['as_of']='2026-06-01'
  with sqlite3.connect(ledger.path)as db:db.execute('update evidence_packs set payload_json=?',(json.dumps(payload),))
 else:
  value=json.loads(scope.read_text());value['assignments'][0]['reason']='another purpose';value['content_digest']=digest({k:v for k,v in value.items()if k!='content_digest'});scope.write_text(json.dumps(value))
 assert n.reading_view(ledger_db=ledger.path,scopes_path=scope)['availability']=='invalid'


def test_missing_audit_is_not_presented_as_a_clean_zero(tmp_path):assert n.reading_view(ledger_db=tmp_path/'missing.sqlite3')['availability']=='missing'

def test_explicit_rebinding_clears_inherited_invocations_and_keeps_evidence(tmp_path):
 old=source_pack();before=old.model_dump(mode='json');new=n.bind_study_identity(old,question='核四通和绝味',object_refs=['603838','603517'],as_of='2026-11-19');assert old.model_dump(mode='json')==before
 assert new.question_scope['object_refs']==['603838','603517']and new.question_scope['as_of']=='2026-11-19';assert new.rows==old.rows and new.applicable_experiences==[]and new.lens_invocations==[];assert new.deterministic_response['request_id']!='old-request';assert new.freshness_manifest['source_dates']=='per_asset'
 with pytest.raises(ValueError):n.bind_study_identity(old,question='',object_refs=['603838'],as_of='2026-11-19')

def test_known_bad_inherited_request_cannot_create_another_record(tmp_path):
 ledger,pack,e,scope,_=sample(tmp_path);n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope)
 with pytest.raises(ValueError,match='quarantined'):ledger.record(ResearchRunCreate(request_id='old-request',question_text='another question',normalized_intent='research',evidence_pack_ids=[pack.pack_id],final_answer='new',validation_report={'valid':True},source_freshness={},agent_surface='test'))
 assert len(ledger.list())==1

def test_bound_study_record_requires_matching_explicit_fields(tmp_path):
 ledger,old,e,scope,_=sample(tmp_path);n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope)
 pack=n.bind_study_identity(old,question='核四通窗口',object_refs=['603838','603517'],as_of='2026-11-19');ledger.store_evidence_pack(pack.model_dump(mode='json'));value=ResearchRunCreate(request_id=pack.deterministic_response['request_id'],question_text=pack.question_scope['question'],normalized_intent='research_question',object_refs=['603838','603517'],evidence_pack_ids=[pack.pack_id],final_answer='新复盘',validation_report={'valid':True},source_freshness=pack.source_freshness,agent_surface='test')
 changed=value.model_copy(update={'object_refs':['002717']})
 with pytest.raises(ValueError,match='record identity differs'):ledger.record(changed)
 row=ledger.record(value);assert row.question_text=='核四通窗口'and row.object_refs==['603838','603517'];assert row.experience_hits==[]
 payload=pack.model_dump(mode='json',exclude={'pack_id','pack_digest'});payload['question_scope']['as_of']='2026-05-26';h=digest(payload);bad=EvidencePack.model_validate({**payload,'pack_id':'EP-'+h[:20].upper(),'pack_digest':h})
 with pytest.raises(ValueError,match='no longer matches'):n.validate_bound_identity(bad)

def test_http_record_refuses_quarantined_identity_without_creating_a_run(tmp_path,monkeypatch):
 import asyncio,httpx,api
 ledger,pack,e,scope,_=sample(tmp_path);n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope);monkeypatch.setattr(api,'research_run_ledger',ledger)
 body=ResearchRunCreate(request_id='old-request',question_text='another topic',normalized_intent='research',evidence_pack_ids=[pack.pack_id],final_answer='answer',validation_report={'valid':True},source_freshness={},agent_surface='test').model_dump(mode='json')
 async def request():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app),base_url='http://test')as client:return await client.post('/api/v1/research/runs',json=body)
 response=asyncio.run(request());assert response.status_code==422 and 'quarantined'in response.json()['detail'];assert len(ledger.list())==1

@pytest.mark.parametrize('field',['future','lens'])
def test_resealed_identity_cannot_restore_inherited_calls_or_claim_future_cutoff(field):
 old=source_pack();pack=n.bind_study_identity(old,question=' 新登记 ',object_refs=['603838'],as_of='2026-11-19');assert pack.question_scope['question']=='新登记'
 payload=pack.model_dump(mode='json',exclude={'pack_id','pack_digest'})
 if field=='lens':payload['lens_invocations']=[{'release_id':'inherited'}]
 else:
  identity=json.loads(payload['validation_catalog']['study_identity_v1']);identity['as_of']='2099-01-01';payload['validation_catalog']['study_identity_v1']=json.dumps(identity)
 h=digest(payload);bad=EvidencePack.model_validate({**payload,'pack_id':'EP-'+h[:20].upper(),'pack_digest':h})
 with pytest.raises(ValueError):n.validate_bound_identity(bad)

def test_quarantined_run_feedback_and_auto_source_eligibility_are_blocked(tmp_path):
 from experience_auto_accept import _existing_run_ids
 from types import SimpleNamespace
 ledger,pack,e,scope,_=sample(tmp_path);n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope)
 with pytest.raises(ValueError,match='before learning feedback'):ledger.add_feedback(e['run_id'],category='reusable_method',feedback_text='review',submitted_by='test')
 assert _existing_run_ids(SimpleNamespace(source_run_refs=[e['run_id']]),ledger)==[]
 with sqlite3.connect(ledger.path)as db:assert db.execute('select count(*) from run_feedback').fetchone()[0]==0

def test_http_feedback_does_not_distill_quarantined_run(tmp_path,monkeypatch):
 import asyncio,httpx,api
 ledger,pack,e,scope,_=sample(tmp_path);n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope);monkeypatch.setattr(api,'research_run_ledger',ledger)
 async def request():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app),base_url='http://test')as client:return await client.post('/api/v1/research/runs/'+e['run_id']+'/feedback',json={'category':'presentation','feedback_text':'readability','submitted_by':'test'})
 response=asyncio.run(request());assert response.status_code==422 and 'before learning feedback'in response.json()['detail']
 with sqlite3.connect(ledger.path)as db:assert db.execute('select count(*) from run_feedback').fetchone()[0]==0

def test_changing_request_id_alone_cannot_reuse_the_quarantined_scope(tmp_path):
 ledger,pack,e,scope,_=sample(tmp_path);n.publish_notes([e],ledger_db=ledger.path,scopes_path=scope)
 with pytest.raises(ValueError,match='changing request ID is not rebinding'):ledger.record(ResearchRunCreate(request_id='different-id',question_text=pack.question_scope['question'],normalized_intent='research',object_refs=['002717'],evidence_pack_ids=[pack.pack_id],final_answer='answer',validation_report={'valid':True},source_freshness={},agent_surface='test'))
 assert len(ledger.list())==1
