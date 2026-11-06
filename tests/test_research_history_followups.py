from copy import deepcopy
from datetime import datetime
import json

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from research_history import prepare_history_records,question_digest
from research_history_followups import add_unanswered_followups,collect_thread_export

THREAD='11111111-1111-4111-8111-111111111111'
FIRST='22222222-2222-4222-8222-222222222222'
NEXT='33333333-3333-4333-8333-333333333333'


def fixture(root):
    def stamp(text):return datetime.fromisoformat(text.replace('Z','+00:00')).timestamp()
    original='请核对这家公司的公告，以及此前已经亏损的情况下应该怎样重新审视自己的判断。'
    expanded=original+'\n\n另外，请区分公告内容和我对截图的推测。'
    source={'schemaVersion':1,'thread':{'id':THREAD,'kind':'chatgpt'},'page':{'hasMore':False},'turns':[
      {'id':FIRST,'status':'completed','startedAt':stamp('2026-06-02T08:00:00Z'),'completedAt':stamp('2026-06-02T08:00:00Z'),'items':[{'type':'userMessage','content':[{'type':'text','text':original}]}]},
      {'id':NEXT,'status':'completed','startedAt':stamp('2026-06-02T08:05:00Z'),'completedAt':stamp('2026-06-02T08:10:00Z'),'items':[{'type':'userMessage','content':[{'type':'text','text':expanded}]},{'type':'agentMessage','text':'原答没有承诺确定的收益。'}]},
    ]}
    rows=[{'id':'QUESTION-'+identity,'kind':'original_question','question':text,'asked_at':at,'symbols':['002514.SZ'],
           'answers':answers,'sources':[{'kind':'chatgpt','thread_id':THREAD,'turn_id':identity}]} for identity,text,at,answers in [
           (FIRST,original,'2026-06-02T08:00:00Z',[]),
           (NEXT,expanded,'2026-06-02T08:05:00Z',[{'text':'原答没有承诺确定的收益。','completed_at':stamp('2026-06-02T08:10:00Z')}])]]
    path=collect_thread_export(json.dumps(source,ensure_ascii=False),[{'unanswered_id':rows[0]['id'],'expanded_id':rows[1]['id']}],root=root)
    return rows,path


def test_expanded_followup_is_a_link_and_never_an_answer_move_or_new_question(tmp_path):
    rows,_=fixture(tmp_path);before=deepcopy(rows)
    prepared=prepare_history_records({'records':rows,'stock_names':{}},root=tmp_path)
    assert rows==before and len(prepared)==2 and prepared[0]['answers']==[]
    assert prepared[1]==rows[1]
    relation=prepared[0]['unanswered_followup']
    assert relation['question_id']==rows[1]['id'] and relation['target_question_digest']==question_digest(rows[1])
    assert relation['source_url']=='https://chatgpt.com/c/'+THREAD
    assert prepared[0]['asked_at']==rows[0]['asked_at'] and prepared[0]['question']==rows[0]['question']


@pytest.mark.parametrize('change',['question','answer','first_answer','first_clock','target_clock','completion_clock','source_thread','source_turn','saved','scope','no_target','duplicate_target','not_expanded','unfinished'])
def test_closeness_and_similar_words_do_not_replace_verified_original_turns(tmp_path,change):
    rows,path=fixture(tmp_path)
    if change=='question':rows[0]['question']='另外一条问题'
    elif change=='answer':rows[1]['answers'][0]['text']='后来改过的答复'
    elif change=='first_answer':rows[0]['answers']=[{'text':'其实已有独立答复'}]
    elif change=='first_clock':rows[0]['asked_at']='2026-06-02T07:59:00Z'
    elif change=='target_clock':rows[1]['asked_at']='2026-06-02T08:06:00Z'
    elif change=='completion_clock':rows[1]['answers'][0]['completed_at']+=60
    elif change=='source_thread':rows[1]['sources'][0]['thread_id']='55555555-5555-4555-8555-555555555555'
    elif change=='source_turn':rows[0]['sources'][0]['turn_id']=NEXT
    elif change=='saved':rows[1]['kind']='saved_research'
    elif change=='scope':rows[1]['symbols']=[]
    elif change=='no_target':rows=rows[:1]
    elif change=='duplicate_target':rows.append(deepcopy(rows[1]))
    elif change=='not_expanded':
        packet=json.loads(path.read_text());source=json.loads(packet['original_output']);source['turns'][1]['items'][0]['content'][0]['text']='另一条内容相似但并非补充的问题'
        rows[1]['question']=source['turns'][1]['items'][0]['content'][0]['text']
        path.rename(path.with_suffix('.retained'))
        collect_thread_export(json.dumps(source,ensure_ascii=False),packet['links'],root=tmp_path)
    else:
        packet=json.loads(path.read_text());source=json.loads(packet['original_output']);source['turns'][0]['status']='inProgress'
        path.rename(path.with_suffix('.retained'))
        collect_thread_export(json.dumps(source,ensure_ascii=False),packet['links'],root=tmp_path)
    assert not any(r.get('unanswered_followup') for r in add_unanswered_followups(rows,root=tmp_path))


def test_import_annotation_cannot_fabricate_a_link_and_source_or_target_changes_withdraw_it(tmp_path):
    rows,path=fixture(tmp_path);prepared=add_unanswered_followups(rows,root=tmp_path)
    assert question_digest(prepared[0])!=question_digest(rows[0])
    changed=deepcopy(prepared);changed[1]['answers'][0]['text']='更正后的原回答'
    withdrawn=add_unanswered_followups(changed,root=tmp_path)
    assert not withdrawn[0].get('unanswered_followup') and question_digest(withdrawn[0])==question_digest(rows[0])
    path.rename(path.with_suffix('.retained'))
    assert not add_unanswered_followups(prepared,root=tmp_path)[0].get('unanswered_followup')


def test_replaying_a_new_export_retains_semantic_identity(tmp_path):
    rows,path=fixture(tmp_path);first=add_unanswered_followups(rows,root=tmp_path)
    packet=json.loads(path.read_text())
    collect_thread_export(packet['original_output'],packet['links'],root=tmp_path)
    assert question_digest(add_unanswered_followups(rows,root=tmp_path)[0])==question_digest(first[0])


def test_original_bytes_and_capture_identity_are_checked_not_just_projected_metadata(tmp_path):
    rows,path=fixture(tmp_path);packet=json.loads(path.read_text())
    packet['original_output']+=' ';packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    path.rename(path.with_suffix('.retained'));atomic_write_json(path.with_name(packet['content_digest']+'.json'),packet)
    with pytest.raises(ValueError,match='original bytes'):add_unanswered_followups(rows,root=tmp_path)
