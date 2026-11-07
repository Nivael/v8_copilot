from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
import research_corrections as c
import research_history as h
from research_repository import ResearchRunCreate, ResearchRunLedger


def sample(tmp_path):
    ledger = ResearchRunLedger(tmp_path/'runs.sqlite3')
    ids = []
    for n, answer in enumerate(['误称原答漏列借款。', '原答已经列出借款，现细化口径。']):
        row = ledger.record(ResearchRunCreate(request_id=str(n), question_text='核对银行借款'+str(n),
            normalized_intent='research', object_refs=['002856'], evidence_pack_ids=['EP-'+'A'*20],
            final_answer=answer, validation_report={'valid': True}, source_freshness={}, agent_surface='test',
            completed_at=f'2026-06-0{n+1}T08:00:00+00:00'))
        ids.append(row.run_id)
    records = h.import_ledger(ledger.path, {'002856.SZ': '*ST美芝'})
    original = {'id': 'QUESTION-original', 'kind': 'original_question', 'asked_at': '2026-05-29T06:00:00Z',
                'question': '债务多吗？', 'answers': [{'text': '长期借款约8664.7万元。'}],
                'sources': [], 'symbols': ['002856.SZ'], 'categories': ['财报与监管']}
    with sqlite3.connect(ledger.path) as db:
        db.row_factory = sqlite3.Row
        runs = {row['run_id']: dict(row) for row in db.execute('select '+','.join(c.FIELDS)+' from research_runs')}
    entry = {'old_run_id': ids[0], 'old_run_digest': digest(runs[ids[0]]),
             'replacement_run_id': ids[1], 'replacement_run_digest': digest(runs[ids[1]]),
             'original_question': {'id': original['id'], 'digest': h.question_digest(original), 'answer_quote': '长期借款约8664.7万元'},
             'headline': '原答已经列出长期借款', 'summary': '此前的遗漏批评撤回；原问原答均保留。',
             'corrected_at': '2026-06-03T08:00:00+00:00'}
    return ledger, [original, *records], entry


def rehash(value):
    value['content_digest'] = digest({k:v for k,v in value.items() if k!='content_digest'})
    return value


def test_exact_original_and_both_runs_are_annotated_without_rewriting_them(tmp_path):
    ledger, records, entry = sample(tmp_path)
    original = deepcopy(records); ledger_before = ledger.path.read_bytes()
    packet = c.publish([entry], ledger_db=ledger.path, records=records)
    actual, runs = c.verified_packet(ledger_db=ledger.path)
    notes = c.annotations(records, actual, runs)
    assert packet == actual
    assert {key:value[0]['role'] for key,value in notes.items()} == {
        records[0]['id']:'original_review', entry['old_run_id']:'corrected_study', entry['replacement_run_id']:'replacement_study'}
    assert records == original and ledger.path.read_bytes() == ledger_before
    assert c.reading_view(ledger_db=ledger.path)['corrections'][0]['headline'] == entry['headline']
    assert (c.correction_path(ledger.path).parent/'history'/(packet['content_digest']+'.json')).is_file()
    assert c.corrected_run_ids(ledger_db=ledger.path) == {entry['old_run_id']}
    assert all('run_digest' not in key for note in notes.values() for key in note[0])


@pytest.mark.parametrize('change', ['quote', 'original_digest', 'missing_original', 'changed_question',
    'changed_answer', 'missing_old', 'changed_saved_answer', 'wrong_saved_source', 'wrong_saved_time'])
def test_changed_original_or_saved_study_prevents_publication(tmp_path, change):
    ledger, records, entry = sample(tmp_path)
    if change == 'quote': entry['original_question']['answer_quote'] = '不存在的原话'
    elif change == 'original_digest': entry['original_question']['digest'] = 'a'*64
    elif change == 'missing_original': records.pop(0)
    elif change == 'changed_question': records[0]['question'] += '另一题'
    elif change == 'changed_answer': records[0]['answers'][0]['text'] = '被改写的旧答'
    elif change == 'missing_old': records.pop(1)
    elif change == 'changed_saved_answer': records[1]['answers'][0]['text'] = '替换过的研究'
    elif change == 'wrong_saved_source': records[1]['sources'][0]['run_id'] = entry['replacement_run_id']
    else: records[1]['asked_at'] = '2026-06-03T08:00:00Z'
    with pytest.raises(ValueError): c.publish([entry], ledger_db=ledger.path, records=records)
    assert not c.correction_path(ledger.path).exists()


@pytest.mark.parametrize('change', ['packet_digest','run_digest','missing_run','blank','future','naive',
                                   'before_new','self','duplicate','cycle','bad_id','extra_field'])
def test_invalid_metadata_cannot_publish_or_silently_reuse_a_correction(tmp_path, change):
    ledger, records, entry = sample(tmp_path)
    packet = c.publish([entry], ledger_db=ledger.path, records=records)
    broken = deepcopy(packet); row = broken['entries'][0]
    if change == 'packet_digest': row['summary'] += '变了'
    elif change == 'run_digest': row['old_run_digest'] = 'b'*64
    elif change == 'missing_run': row['replacement_run_id'] = 'RUN-'+'B'*24
    elif change == 'blank': row['headline'] = ' '
    elif change == 'future': row['corrected_at'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    elif change == 'naive': row['corrected_at'] = '2026-06-03T08:00:00'
    elif change == 'before_new': row['corrected_at'] = '2026-06-01T08:00:00Z'
    elif change == 'self': row['replacement_run_id'] = row['old_run_id']
    elif change == 'duplicate': broken['entries'].append(deepcopy(row))
    elif change == 'cycle': broken['entries'].append({**row,'old_run_id':row['replacement_run_id'],'replacement_run_id':row['old_run_id']})
    elif change == 'bad_id': row['old_run_id'] = 'another record'
    else: row['status'] = 'verified'
    if change != 'packet_digest': rehash(broken)
    atomic_write_json(c.correction_path(ledger.path), broken)
    assert c.reading_view(ledger_db=ledger.path) == {'availability':'updating','corrections':[]}
    with pytest.raises(ValueError): c.verified_packet(ledger_db=ledger.path)


@pytest.mark.parametrize('field', list(c.FIELDS[1:]))
def test_changed_ledger_fields_withdraw_the_reading_note(tmp_path, field):
    ledger, records, entry = sample(tmp_path)
    c.publish([entry], ledger_db=ledger.path, records=records)
    with sqlite3.connect(ledger.path) as db:
        db.execute('update research_runs set '+field+'=? where run_id=?', ('changed',entry['replacement_run_id']))
    assert c.reading_view(ledger_db=ledger.path)['availability'] == 'updating'


@pytest.mark.parametrize('change', ['unvalidated', 'different_subject', 'earlier'])
def test_rehashing_cannot_turn_unrelated_or_unvalidated_run_into_a_replacement(tmp_path, change):
    ledger, records, entry = sample(tmp_path)
    field,value = {'unvalidated':('validation_report_json','{"valid":false}'),
                   'different_subject':('object_refs_json','["603398"]'),
                   'earlier':('completed_at','2026-05-29T00:00:00Z')}[change]
    with sqlite3.connect(ledger.path) as db:
        db.execute('update research_runs set '+field+'=? where run_id=?',(value,entry['replacement_run_id']))
        db.row_factory=sqlite3.Row
        run=dict(db.execute('select '+','.join(c.FIELDS)+' from research_runs where run_id=?',(entry['replacement_run_id'],)).fetchone())
    entry['replacement_run_digest']=digest(run)
    with pytest.raises(ValueError): c.publish([entry],ledger_db=ledger.path,records=records)


def history_source(root, records):
    import research_history_prices
    calendar=['2026-05-28','2026-05-29','2026-06-01','2026-06-02','2026-06-03']
    points=[{'date':day,'value':100,'level':100} for day in calendar]
    paths={'calendar':calendar,'stocks':{'002856.SZ':{'name':'*ST美芝','points':points}},'market':points,'st':points,
           'st_name':'ST参考','st_note':'测试','st_source_url':'https://example.com/'}
    body={'data':paths,'processor_digest':sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest()}
    atomic_write_json(root/'price_paths/current.json',rehash(body))
    return {'records':records,'sources':[]}


def test_published_history_withdraws_stale_or_omitted_notes_without_changing_returns(tmp_path):
    ledger, records, entry = sample(tmp_path)
    c.publish([entry],ledger_db=ledger.path,records=records)
    root=tmp_path/'research_history'; imported=history_source(root,records)
    original=deepcopy(imported)
    packet=h.publish(imported,root=root,ledger_db=ledger.path)
    detail=h.load('002856.SZ',root=root,ledger_db=ledger.path)
    assert detail['questions'][0]['research_corrections'][0]['role']=='original_review'
    plain=h.assemble(records,json.loads((root/'price_paths/current.json').read_text())['data'])
    assert [{k:v for k,v in q.items() if k!='research_corrections'} for q in detail['questions']] == plain['details']['002856.SZ']['questions']
    assert imported==original
    packet['details']['002856.SZ']['questions'][0].pop('research_corrections')
    atomic_write_json(root/'current.json',rehash(packet))
    assert h.load(root=root,ledger_db=ledger.path)=={'availability':'updating'}
    h.publish(imported,root=root,ledger_db=ledger.path)
    entry['summary']='补充更正说明'
    c.publish([entry],ledger_db=ledger.path,records=records)
    assert h.load(root=root,ledger_db=ledger.path)=={'availability':'updating'}
    h.publish(imported,root=root,ledger_db=ledger.path)
    assert h.load(root=root,ledger_db=ledger.path)['availability']=='available'


def test_missing_packet_has_no_notes_and_does_not_create_a_database(tmp_path):
    ledger=tmp_path/'missing.sqlite3'
    assert c.reading_view(ledger_db=ledger)['corrections']==[]
    assert not ledger.exists()


@pytest.mark.parametrize('change', ['missing', 'emptied'])
def test_missing_published_notes_cannot_redisplay_the_old_run_as_uncorrected(tmp_path, change):
    ledger,records,entry=sample(tmp_path)
    c.publish([entry],ledger_db=ledger.path,records=records)
    root=tmp_path/'research_history'
    h.publish(history_source(root,records),root=root,ledger_db=ledger.path)
    if change=='missing': c.correction_path(ledger.path).unlink()
    else: atomic_write_json(c.correction_path(ledger.path),rehash({'version':c.VERSION,'entries':[]}))
    assert c.reading_view(ledger_db=ledger.path)['availability']=='updating'
    with pytest.raises(ValueError,match='missing or out of date'):
        c.corrected_run_ids(ledger_db=ledger.path)


def test_current_company_judgments_do_not_fall_back_to_corrected_old_study(tmp_path):
    from case_research_scopes import mark_historical_review
    from workbench_views import learning_view
    ledger,records,entry=sample(tmp_path)
    c.publish([entry],ledger_db=ledger.path,records=records)
    scopes=tmp_path/'scopes'
    mark_historical_review(entry['replacement_run_id'],'历史核查',ledger_db=ledger.path,directory=scopes)
    result=learning_view({'market':{},'watch_bases':[{'symbol':'002856.SZ','name':'*ST美芝','availability':'unavailable'}]},
        ledger_db=ledger.path,experience_db=tmp_path/'none',run_scopes_path=scopes/'current.json')
    assert result['cases'][0]['research_count']==0 and result['cases'][0]['history']==[]


def test_readonly_correction_endpoint_keeps_the_recorded_run_contract_unchanged(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import api
    ledger,records,entry=sample(tmp_path)
    c.publish([entry],ledger_db=ledger.path,records=records)
    monkeypatch.setattr(api,'research_run_ledger',ledger)
    before=ledger.path.read_bytes()
    with TestClient(api.app) as client:
        result=client.get('/api/v1/research/corrections')
        assert result.status_code==200 and result.json()['corrections'][0]['old_run_id']==entry['old_run_id']
        recorded=client.get('/api/v1/research/runs/'+entry['old_run_id']).json()
        assert recorded['final_answer']==records[1]['answers'][0]['text']
        assert 'corrections' not in recorded
    assert ledger.path.read_bytes()==before


def legacy_subject_sample(tmp_path, *, new_question='债务多吗？', old_question='债务多吗？', mutation=None):
    ledger, records, entry=sample(tmp_path)
    # Build immutable evidence packs as they would be saved by validated studies.
    with sqlite3.connect(ledger.path) as db:
        for prefix,question in [('old',old_question),('replacement',new_question)]:
            run_id=entry[prefix+'_run_id'];row={'row_id':prefix,'question_id':entry['original_question']['id'],'question':question}
            if mutation=='foreign_question_id' and prefix=='old':row['question_id']='foreign'
            pack={'rows':[row],'validation_catalog':{'query_row:'+prefix:json.dumps({k:v for k,v in row.items() if k!='row_id'},ensure_ascii=False,sort_keys=True)}}
            key=digest(pack);pack_id='EP-'+key[:20].upper();pack.update(pack_id=pack_id,pack_digest=key)
            if mutation=='uncatalogued' and prefix=='old':pack['validation_catalog']={}
            db.execute('insert into evidence_packs values (?,?,?,?)',(pack_id,key,json.dumps(pack),'2026-06-01T00:00:00Z'))
            validation={'valid':True,'pack_id':pack_id,'pack_digest':key}
            if mutation=='unvalidated_pack' and prefix=='old':validation['pack_digest']='b'*64
            db.execute('update research_runs set object_refs_json=?,evidence_pack_ids_json=?,validation_report_json=? where run_id=?',
                (json.dumps(['unknown' if prefix=='old' else 'comparison:002856,603272']),json.dumps([pack_id]),json.dumps(validation),run_id))
        db.commit();db.row_factory=sqlite3.Row
        for prefix in ('old','replacement'):
            record=dict(db.execute('select '+','.join(c.FIELDS)+' from research_runs where run_id=?',(entry[prefix+'_run_id'],)).fetchone())
            entry[prefix+'_run_digest']=digest(record)
    return ledger,records,entry


def test_legacy_unknown_correction_requires_both_validated_original_rows(tmp_path):
    ledger,records,entry=legacy_subject_sample(tmp_path)
    before=ledger.path.read_bytes();packet=c.publish([entry],ledger_db=ledger.path,records=records)
    actual,runs=c.verified_packet(ledger_db=ledger.path)
    assert actual==packet and c.annotations(records,actual,runs,ledger_db=ledger.path)[records[0]['id']]
    assert ledger.path.read_bytes()==before


@pytest.mark.parametrize('mutation', ['foreign_question_id','uncatalogued','unvalidated_pack','different_original','both_wrong_original','no_original_binding'])
def test_unrelated_legacy_studies_cannot_be_linked_by_manual_display_scope(tmp_path,mutation):
    kwargs={}
    if mutation=='different_original':kwargs['new_question']='另一问题'
    if mutation=='both_wrong_original':kwargs.update(old_question='另一问题',new_question='另一问题')
    ledger,records,entry=legacy_subject_sample(tmp_path,mutation=mutation,**kwargs)
    if mutation=='no_original_binding':entry['original_question']=None
    with pytest.raises(ValueError):c.publish([entry],ledger_db=ledger.path,records=records)
    assert not c.correction_path(ledger.path).exists()
