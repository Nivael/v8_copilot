"""Bound reading-only identity corrections. Never update original SQLite runs."""
from datetime import date,datetime,timezone
import json,re,sqlite3
from pathlib import Path
from canonical_json import digest,canonical_json
from case_research_scopes import OUTPUT as SCOPES,load_scopes,RUN_FIELDS
from data_refresh import atomic_write_json
from settings import RESEARCH_RUN_LEDGER_DB
VERSION='research_identity_notes_v1'

def note_path(ledger_db=RESEARCH_RUN_LEDGER_DB):return ledger_db.parent/'research_identity_notes/current.json'

def packet(entries):
 body={'version':VERSION,'entries':entries};return {**body,'content_digest':digest(body)}

def validate_shape(value):
 if set(value)!={'version','entries','content_digest'}or value['version']!=VERSION or value['content_digest']!=digest({k:v for k,v in value.items()if k!='content_digest'})or not isinstance(value['entries'],list):raise ValueError('identity note packet changed')
 seen=set()
 for e in value['entries']:
  if set(e)!={'run_id','run_digest','original_pack_id','original_scope_digest','corrected_question','corrected_object_refs','corrected_research_as_of','purpose_basis','reviewed_at','experience_context','topic_changed','original_request_id'}:raise ValueError('invalid identity note fields')
  if not re.fullmatch(r'RUN-[A-F0-9]{24}',e['run_id'])or e['run_id']in seen:raise ValueError('duplicate or invalid identity run')
  seen.add(e['run_id'])
  if not all(isinstance(e[k],str)and re.fullmatch('[a-f0-9]{64}',e[k])for k in ['run_digest','original_scope_digest']):raise ValueError('invalid identity binding')
  if not re.fullmatch('EP-[A-F0-9]{20}',e['original_pack_id'])or not isinstance(e['corrected_question'],str)or not 1<=len(e['corrected_question'].strip())<=800:raise ValueError('invalid identity question')
  refs=e['corrected_object_refs']
  if not isinstance(refs,list)or not 1<=len(refs)<=50 or len(set(refs))!=len(refs)or not all(isinstance(r,str)and re.fullmatch('[A-Za-z0-9_-]{1,128}',r)for r in refs):raise ValueError('invalid corrected objects')
  clock=datetime.fromisoformat(e['reviewed_at']);cutoff=date.fromisoformat(e['corrected_research_as_of'])
  if clock.tzinfo is None or clock>datetime.now(timezone.utc)or cutoff>clock.date()or e['experience_context']!='inherited_unreviewed'or type(e['topic_changed'])is not bool or not isinstance(e['purpose_basis'],str)or not 1<=len(e['purpose_basis'])<=400 or not isinstance(e['original_request_id'],str)or not 1<=len(e['original_request_id'])<=128:raise ValueError('invalid identity date or context')
 return value

def validated_rows(value,*,ledger_db=RESEARCH_RUN_LEDGER_DB,scopes_path=SCOPES/'current.json'):
 validate_shape(value);roles={e['run_id']:e for e in load_scopes(scopes_path)['assignments']};result=[]
 with sqlite3.connect(ledger_db.as_uri()+'?mode=ro',uri=True)as db:
  db.row_factory=sqlite3.Row
  for e in value['entries']:
   raw=db.execute('select * from research_runs where run_id=?',(e['run_id'],)).fetchone()
   if raw is None or digest(dict(raw))!=e['run_digest']:raise ValueError('identity note no longer matches original run')
   r=dict(raw);role=roles.get(e['run_id'])
   if not role or role['run_digest']!=digest({k:r[k]for k in RUN_FIELDS})or role['reason']!=e['purpose_basis']:raise ValueError('identity purpose binding changed')
   if e['original_request_id']!=r['request_id']or e['original_pack_id']not in json.loads(r['evidence_pack_ids_json']):raise ValueError('identity original pack changed')
   saved=db.execute("select json_extract(payload_json,'$.question_scope') as scope from evidence_packs where pack_id=?",(e['original_pack_id'],)).fetchone()
   if saved is None:raise ValueError('identity pack missing')
   scope=json.loads(saved['scope'])
   if digest(scope)!=e['original_scope_digest']or scope['question']!=r['question_text']:raise ValueError('identity original scope changed')
   if datetime.fromisoformat(e['reviewed_at'])<datetime.fromisoformat(r['completed_at']):raise ValueError('identity note predates run')
   if e['topic_changed']!=(e['corrected_question']!=r['question_text']):raise ValueError('identity change classification differs')
   result.append({**e,'original_question':r['question_text'],'original_object_refs':json.loads(r['object_refs_json']),'original_research_as_of':scope.get('as_of'),'original_experience_hits':json.loads(r['experience_hits_json'])})
 return result

def publish_notes(entries,*,ledger_db=RESEARCH_RUN_LEDGER_DB,scopes_path=SCOPES/'current.json',directory=None):
 target=directory or note_path(ledger_db).parent;current=target/'current.json'
 old=validate_shape(json.loads(current.read_text()))if current.exists()else packet([])
 ids={e['run_id']for e in old['entries']}
 if any(e['run_id']in ids for e in entries):raise ValueError('identity notes are append-only')
 value=packet([*old['entries'],*entries]);validated_rows(value,ledger_db=ledger_db,scopes_path=scopes_path)
 atomic_write_json(target/'history'/(value['content_digest']+'.json'),value);atomic_write_json(current,value);return value

def reading_view(*,ledger_db=RESEARCH_RUN_LEDGER_DB,scopes_path=SCOPES/'current.json',path=None):
 path=path or note_path(ledger_db)
 if not path.exists():return {'availability':'missing','corrections':[],'boundary':'身份核对登记尚未建立，不能当已审零错误。'}
 try:
  value=validate_shape(json.loads(path.read_text()));rows=validated_rows(value,ledger_db=ledger_db,scopes_path=scopes_path)
  return {'availability':'available','content_digest':value['content_digest'],'corrections':rows,'boundary':'只校正阅读身份；原研究、原证据包、原方法命中和原时间戳保持。其他记录未因此认证。'}
 except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):return {'availability':'invalid','corrections':[],'boundary':'身份更正未通过原记录绑定核对，不沿用更正标签。'}

def bind_study_identity(pack,*,question,object_refs,as_of):
 """Explicitly bind a new review; inherited retrieval and Lens calls are not new usage."""
 from evidence_gateway import EvidencePack
 if not isinstance(question,str)or not 1<=len(question.strip())<=800 or not object_refs or len(object_refs)>50 or len(set(object_refs))!=len(object_refs)or not all(isinstance(x,str)and re.fullmatch('[A-Za-z0-9_-]{1,128}',x)for x in object_refs):raise ValueError('explicit study identity required')
 cutoff=date.fromisoformat(as_of)
 if cutoff>datetime.now(timezone.utc).date():raise ValueError('future study cutoff')
 question=question.strip()
 identity={'question':question,'object_refs':list(object_refs),'as_of':as_of,'mode':'historical_review'};key='study-'+digest(identity)[:24]
 payload=pack.model_dump(mode='json',exclude={'pack_id','pack_digest'});payload['question_scope']={'question':question,'object':{'kind':'stock'if len(object_refs)==1 and re.fullmatch('[0-9]{6}',object_refs[0])else'research_scope','ref':object_refs[0]},'object_refs':list(object_refs),'intent':'research_question','route':'historical_material_review','matched_rules':[],'as_of':as_of}
 payload['query_plan_id']=key;payload['deterministic_response']={'request_id':key,'mode':'historical_review'};payload['applicable_experiences']=[];payload['lens_invocations']=[];payload['source_freshness']={'research_cutoff':as_of,'source_dates':'mixed; retain individual saved source dates'};payload['freshness_manifest']={'status':'historical_review','research_cutoff':as_of,'source_dates':'per_asset','inherited_manifest_digest':digest(pack.freshness_manifest)}
 payload['provenance'].append('inherited_evidence_bank:'+pack.pack_id);payload['validation_catalog']['study_identity_v1']=canonical_json(identity);payload['provenance'].append('explicit_study_identity:'+digest(identity))
 h=digest(payload);return EvidencePack.model_validate({**payload,'pack_id':'EP-'+h[:20].upper(),'pack_digest':h})

def validate_bound_identity(pack):
 raw=pack.validation_catalog.get('study_identity_v1')
 if raw is None:raise ValueError('explicit study identity binding missing')
 identity=json.loads(raw)
 if set(identity)!={'question','object_refs','as_of','mode'}or identity['mode']!='historical_review':raise ValueError('invalid explicit study identity')
 if not isinstance(identity['question'],str)or not 1<=len(identity['question'])<=800 or not isinstance(identity['object_refs'],list)or not 1<=len(identity['object_refs'])<=50 or not all(isinstance(x,str)and re.fullmatch('[A-Za-z0-9_-]{1,128}',x)for x in identity['object_refs'])or len(set(identity['object_refs']))!=len(identity['object_refs'])or not isinstance(identity['as_of'],str):raise ValueError('invalid explicit identity values')
 if date.fromisoformat(identity['as_of'])>datetime.now(timezone.utc).date():raise ValueError('future study cutoff')
 key='study-'+digest(identity)[:24];scope=pack.question_scope
 if (scope.get('intent')!='research_question'or scope.get('route')!='historical_material_review'or scope.get('matched_rules')!=[]or scope.get('question')!=identity['question']or scope.get('object_refs')!=identity['object_refs']or scope.get('as_of')!=identity['as_of']or scope.get('object',{}).get('ref')!=identity['object_refs'][0]or pack.query_plan_id!=key or pack.deterministic_response.get('request_id')!=key or pack.source_freshness.get('research_cutoff')!=identity['as_of']or pack.freshness_manifest.get('research_cutoff')!=identity['as_of']or pack.applicable_experiences or pack.lens_invocations):raise ValueError('explicit study identity no longer matches its pack')
 return identity

def guard_record_identity(value,ledger_db):
 path=note_path(ledger_db)
 if path.exists():
  notes=validate_shape(json.loads(path.read_text()))
  if any(e['original_request_id']==value.request_id for e in notes['entries']):raise ValueError('inherited study request identity is quarantined; explicitly rebind the current study')
 if path.exists() and ledger_db.exists():
  blocked_scopes={e['original_scope_digest']for e in notes['entries']}
  with sqlite3.connect(ledger_db.as_uri()+'?mode=ro',uri=True)as db:
   for pack_id in value.evidence_pack_ids:
    saved=db.execute("select json_extract(payload_json,'$.question_scope') from evidence_packs where pack_id=?",(pack_id,)).fetchone()
    if saved and saved[0] and digest(json.loads(saved[0]))in blocked_scopes:raise ValueError('inherited study scope is quarantined; changing request ID is not rebinding')
 if not value.request_id.startswith('study-'):return
 from evidence_gateway import EvidencePack
 if len(value.evidence_pack_ids)!=1 or not ledger_db.exists():raise ValueError('explicit study requires one stored bound pack')
 with sqlite3.connect(ledger_db.as_uri()+'?mode=ro',uri=True)as db:
  row=db.execute('select payload_json from evidence_packs where pack_id=?',(value.evidence_pack_ids[0],)).fetchone()
 if row is None:raise ValueError('explicit study pack not stored')
 pack=EvidencePack.model_validate_json(row[0]);identity=validate_bound_identity(pack)
 if value.request_id!=pack.deterministic_response['request_id']or value.question_text!=identity['question']or value.object_refs!=identity['object_refs']or value.source_freshness!=pack.source_freshness or value.normalized_intent!=pack.question_scope['intent']:raise ValueError('record identity differs from its bound pack')

def quarantined_run_ids(ledger_db):
 path=note_path(ledger_db)
 if not path.exists():return set()
 return {e['run_id']for e in validate_shape(json.loads(path.read_text()))['entries']}

def guard_feedback_identity(run_id,ledger_db):
 if run_id in quarantined_run_ids(ledger_db):raise ValueError('research identity requires explicit rebinding before learning feedback')
