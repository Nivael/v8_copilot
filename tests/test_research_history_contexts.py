from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from research_history import add_question_contexts,assemble,prepare_history_records,publish,question_digest
from research_history_captures import collect_outputs,import_capture_files
from research_history_reviews import freeze_review
from test_research_history import sample
from test_research_history_captures import capture,log_capture,Q1,Q2,THREAD


def originals(tmp_path):
    packet=capture();packet['title']='宝馨原聊天'
    parent,child=packet['turns']
    parent.update(question='这份材料是否会影响后续进度？',date_marker='2026-06-02T02:00:00Z',date_marker_owner=Q1)
    child.update(question='就是这个',date_marker=parent['date_marker'],date_marker_owner=Q1,attachment_count=1,
                 answers=[{'text':'原答只给出了一个可能性。'}])
    collect_outputs(log_capture(tmp_path,packet),tmp_path/'captures/cua_v1')
    rows,_=import_capture_files(tmp_path/'captures/cua_v1',{'002514.SZ':'*ST宝馨'})
    return rows


def test_followup_quotes_a_verified_group_opener_without_rewriting_original_or_inventing_image(tmp_path):
    rows=originals(tmp_path);unchanged=deepcopy(rows);result=add_question_contexts(rows,rows)
    child=result[1];context=child['question_context']
    assert rows==unchanged and child['question']=='就是这个' and child['asked_at'] is None
    assert context['question']==rows[0]['question'] and context['question_id']=='QUESTION-'+Q1
    assert context['source_url']=='https://chatgpt.com/c/'+THREAD and context['source_capture_digests']
    assert child['unavailable_attachments']==1 and not result[0].get('question_context')


@pytest.mark.parametrize('change',['unknown_owner','wrong_thread','wrong_day','wrong_clock','not_group_opener','changed_parent','no_parent','own_clock','zero_offset','canonical_clock','canonical_offset','canonical_marker','corrected_parent_clock','date_only_parent'])
def test_nearby_dates_or_unverified_metadata_do_not_establish_followup_context(tmp_path,change):
    captured=originals(tmp_path);records=deepcopy(captured)
    if change=='unknown_owner':records[1]['source_date_owner_id']=None
    elif change=='wrong_thread':
        for row in [records[1],captured[1]]:row['sources'][0]['thread_id']='55555555-5555-4555-8555-555555555555'
    elif change=='wrong_day':
        for row in [records[1],captured[1]]:row.update(asked_on='2026-06-03',source_date_marker='2026-06-03T02:00:00Z')
    elif change=='wrong_clock':
        for row in [records[1],captured[1]]:row['source_date_marker']='2026-06-02T03:00:00Z'
    elif change=='not_group_opener':captured[0]['source_date_owner_id']=None
    elif change=='changed_parent':records[0]['question']='后来更正了的另一份材料'
    elif change=='no_parent':records=records[1:]
    elif change=='own_clock':captured[1]['asked_at']='2026-06-02T03:00:00Z'
    elif change=='zero_offset':captured[1]['source_group_offset']=0
    elif change=='canonical_clock':records[1]['asked_at']='2026-06-02T03:00:00Z'
    elif change=='canonical_offset':records[1]['source_group_offset']=0
    elif change=='canonical_marker':records[1]['source_date_marker']='2026-06-02T03:00:00Z'
    elif change=='corrected_parent_clock':records[0]['asked_at']='2026-06-02T03:00:00Z'
    else:records[0].update(asked_at=None,asked_on='2026-06-02',time_precision='day')
    result=add_question_contexts(records,captured)
    assert not any(row.get('question_context') for row in result)


def test_replaying_another_capture_keeps_review_but_changed_context_withdraws_it(tmp_path):
    rows=originals(tmp_path);prepared=add_question_contexts(rows,rows);parent,child=prepared;paths,_=sample()
    review=freeze_review({'question_digest':question_digest(child),'then_quote':'一个可能性','headline':'保留条件边界'},child,paths,'2026-06-02')
    replay=deepcopy(rows)
    for row in replay:row['sources'][0]['capture_digest']='another-complete-capture'
    again=add_question_contexts(rows,[*rows,*replay])
    assert question_digest(again[1])==question_digest(child)
    assert assemble(again,paths,reviews={child['id']:review})['details']['002514.SZ']['questions'][1]['review']==review
    corrected=deepcopy(rows);corrected[0]['question']='这次实际在问另一份材料的处理期限'
    changed=add_question_contexts(corrected,corrected)
    state=assemble(changed,paths,reviews={child['id']:review})['details']['002514.SZ']['questions'][1]
    assert state['review'] is None and state['previous_review']==review and state['review_status']=='original_changed'
    # Losing the independent capture also withdraws its context-bound assessment.
    missing=add_question_contexts(prepared,[])
    assert 'question_context' not in missing[1] and question_digest(missing[1])!=question_digest(child)


def test_ambiguous_message_alias_does_not_select_a_convenient_context(tmp_path):
    rows=originals(tmp_path);other=deepcopy(rows[0]);other['id']='different-canonical-record'
    assert not add_question_contexts([*rows,other],rows)[1].get('question_context')


def test_publication_rebuilds_context_from_bound_originals_not_an_imported_annotation(tmp_path):
    rows=originals(tmp_path);imported={'records':rows,'stock_names':{'002514.SZ':'*ST宝馨'},'sources':[]}
    rows[1]['question_context']={'question':'未经来源支持的解释'}
    prepared=prepare_history_records(imported,root=tmp_path)
    assert prepared[1]['question_context']['question']==rows[0]['question']
    import research_history_prices
    paths,_=sample();body={'data':paths,'processor_digest':sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest()};body['content_digest']=digest(body)
    atomic_write_json(tmp_path/'price_paths/current.json',body)
    value=publish(imported,root=tmp_path)
    child=next(q for q in value['details']['002514.SZ']['questions'] if q['id']=='QUESTION-'+Q2)
    assert child['question']=='就是这个' and child['question_context']['question_id']=='QUESTION-'+Q1
