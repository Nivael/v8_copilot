from copy import deepcopy
from datetime import datetime,timezone
import json

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from research_history import assemble,deduplicate,mark_answer_bindings,question_day,question_digest
from research_history_captures import PREFIX,collect_outputs,import_capture_files,merge_records,validate_capture
from test_research_history import sample


THREAD='11111111-1111-4111-8111-111111111111'
Q1='22222222-2222-4222-8222-222222222222'
Q2='33333333-3333-4333-8333-333333333333'


def capture():
    return {'version':'history_dom_capture_v1','thread_id':THREAD,'title':'沐邦年报分析与风险',
            'url':'https://chatgpt.com/c/'+THREAD,'captured_at':'2026-07-07T00:00:00Z','loading_older':True,
            'turns':[{'id':Q1,'question':'应该减一点吗','date_marker':'2026-07-06T02:22:44.891Z','has_own_time':True,'group_offset':0,'answers':[{'text':'先核查风险。','id':'44444444-4444-4444-8444-444444444444'}]},
                     {'id':Q2,'question':'那现在呢','date_marker':'2026-07-06T02:22:44.891Z','has_own_time':False,'group_offset':1,'answers':[]}]}


def log_capture(tmp_path,value=None,namespace='mcp__cua_repl'):
    value=value or capture();text=PREFIX+json.dumps(value,ensure_ascii=False)
    events=[{'type':'response_item','payload':{'type':'function_call','namespace':namespace,'name':'js','call_id':'capture'}},
            {'type':'response_item','payload':{'type':'reasoning','text':'Do not import this as a question'}},
            {'type':'response_item','payload':{'type':'function_call_output','call_id':'capture','output':[{'type':'input_text','text':text}]}}]
    path=tmp_path/'explicit-owner-tool-log.jsonl';path.write_text('\n'.join(json.dumps(e,ensure_ascii=False) for e in events)+'\n');return path


def test_capture_selects_only_marked_returned_cua_output_and_preserves_original_bytes(tmp_path):
    log=log_capture(tmp_path);folder=tmp_path/'captures';paths=collect_outputs(log,folder)
    assert len(paths)==1 and collect_outputs(log,folder)==paths
    rows,sources=import_capture_files(folder,{'603398.SH':'*ST沐邦'})
    assert len(rows)==2 and all(r['symbols']==['603398.SH'] for r in rows)
    assert rows[0]['asked_at']=='2026-07-06T02:22:44.891000+00:00'
    assert rows[1]['asked_at'] is None and rows[1]['asked_on']=='2026-07-06'
    assert rows[1]['time_precision']=='day' and rows[1]['source_group_offset']==1
    assert rows[0]['answers'][0]['text']=='先核查风险。'
    assert 'not a claim of complete thread' in sources[0]['capture_scope']
    wrong=tmp_path/'wrong';assert not collect_outputs(log_capture(tmp_path,namespace='functions'),wrong)


def test_rehashed_projection_cannot_change_returned_original(tmp_path):
    paths=collect_outputs(log_capture(tmp_path),tmp_path/'captures');value=json.loads(paths[0].read_text())
    value['capture']['turns'][0]['question']='changed'
    value['content_digest']=digest({k:v for k,v in value.items() if k!='content_digest'});atomic_write_json(paths[0],value)
    with pytest.raises(ValueError,match='original capture changed'):import_capture_files(paths[0].parent,{'603398.SH'})


def test_independent_timestamp_required_and_thread_url_identity_cannot_drift():
    original=capture()
    changed=deepcopy(original);changed['url']='https://chatgpt.com/c/'+Q1
    with pytest.raises(ValueError,match='URL mismatch'):validate_capture(changed)
    changed=deepcopy(original);changed['turns'][0]['date_marker']=None
    with pytest.raises(ValueError,match='timestamp'):validate_capture(changed)
    changed=deepcopy(original);changed['turns'][0]['date_marker']='2099-01-01T00:00:00Z'
    with pytest.raises(ValueError,match='future question'):validate_capture(changed)
    changed=deepcopy(original);changed['turns'][0]['date_marker_owner']=Q2
    with pytest.raises(ValueError,match='owner mismatch'):validate_capture(changed)


def test_capture_merge_keeps_exact_original_time_and_replaying_branch_occurrences_is_idempotent(tmp_path):
    collect_outputs(log_capture(tmp_path),tmp_path/'captures');rows,_=import_capture_files(tmp_path/'captures',{'603398.SH'})
    first=deepcopy(rows[0]);first['sources']=[{'kind':'chatgpt','turn_id':Q1}]
    incomplete=deepcopy(rows[0]);incomplete.update(asked_at=None,time_precision='day')
    assert merge_records([first],[incomplete])[0]['asked_at']==first['asked_at']
    retry=deepcopy(rows[1]);retry['question']=rows[0]['question']
    merged=deduplicate(merge_records([rows[0]],[retry]))
    assert len(merged)==1 and len(merged[0]['occurrences'])==2
    replay=deduplicate(merge_records(merged,[rows[0],retry]))
    assert len(replay)==1 and replay[0]['retry_or_branch_count']==2
    assert len(replay[0]['sources'])==2


def test_clean_user_content_replaces_bubble_controls_but_does_not_rewrite_original_tool_text(tmp_path):
    collect_outputs(log_capture(tmp_path),tmp_path/'captures');rows,_=import_capture_files(tmp_path/'captures',{'603398.SH'})
    bubble=deepcopy(rows[0]);bubble['question']='应该减一点吗…Show more'
    content=deepcopy(rows[0]);content['question_representation']='user_content'
    corrected=merge_records([bubble],[content])[0]
    assert corrected['question']=='应该减一点吗' and corrected['question_representation']=='user_content'
    tool=deepcopy(rows[0]);tool.pop('question_representation');tool['question']='原工具返回的文字';tool['sources']=[{'kind':'chatgpt','turn_id':Q1}]
    assert merge_records([tool],[content])[0]['question']=='原工具返回的文字'


def test_day_precision_does_not_fabricate_question_time_and_uses_explicit_retrospective_close():
    paths,r=sample();r.update(asked_at=None,asked_on='2026-06-02',time_precision='day',source_date_marker='2026-06-02T02:00:00Z',source_group_offset=1)
    row=assemble([r],paths)['details']['002514.SZ']['questions'][0]
    assert row['asked_at'] is None and row['asked_on']=='2026-06-02'
    assert row['anchor_date']=='2026-06-02' and row['anchor_basis']=='date_only_retrospective_close'
    assert '事后' in row['basis_note']
    changed=deepcopy(r);changed['asked_on']='2026-06-03'
    assert question_digest(changed)!=question_digest(r)
    with pytest.raises(ValueError,match='date group mismatch'):deduplicate([changed])


def test_answer_completed_after_close_cannot_be_graded_against_a_pre_answer_daily_move():
    paths,r=sample();r['asked_at']='2026-06-02T06:45:00Z';r['answers'][0]['completed_at']='2026-06-02T07:08:00Z'
    row=assemble([r],paths)['details']['002514.SZ']['questions'][0]
    assert row['anchor_date']=='2026-06-02' and row['anchor_basis']=='original_answer_time'
    assert row['outcomes']['stock']['one_day']['date']=='2026-06-03'
    assert '较晚时点' in row['basis_note']


def test_final_answer_shared_by_two_steering_questions_is_not_labeled_an_independent_reply():
    _,r=sample();r['answers'][0].update(completed_at='2026-06-02T09:00:00Z',source_thread_id='source')
    other=deepcopy(r);other['id']='followup';other['question']='还有一个问题'
    rows=mark_answer_bindings([r,other])
    assert all(row['answers'][0]['binding']=='shared_turn_answer' for row in rows)
    assert rows[0]['answers'][0]['source_question_ids']==['followup','question']
