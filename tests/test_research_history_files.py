from copy import deepcopy
from hashlib import sha256
import pytest
from research_history import assemble,load_file,question_digest
from research_history_files import archive_file,add_files
from research_history_reviews import freeze_review
from test_research_history_visuals import PNG,original,publish_fixture,THREAD,MESSAGE


def observation(media='image'):
    return {'version':'history_download_observation_v1','source_message_id':MESSAGE,'source_thread_id':THREAD,'source_url':'https://chatgpt.com/c/'+THREAD,
            'question_id':'QUESTION-'+MESSAGE,'question':original()['question'],'media_kind':media,'label':'当时的附件','observed_at':'2026-06-03T00:00:00Z',
            'attachment_index':0,'attachment_count':1,'binding_record_sha256':'a'*64,'download_record_sha256':'b'*64,'binding_tool_call_id':'binding','download_tool_call_id':'download',
            **({'file_name':'playbook.md'} if media=='document' else {})}


def test_message_bound_text_and_image_copies_stay_distinct_and_are_served_verbatim(tmp_path):
    row=original();row['question']+='\n[User attached 1 file; file contents were not included]';before=deepcopy(row)
    text='# 原来的参考\n\n这是原文，不是本次判断。'.encode()
    for media,raw in [('image',PNG),('document',text)]:archive_file(raw,{**observation(media),'question':row['question']},root=tmp_path)
    prepared=add_files([row],root=tmp_path)[0];assert row==before
    assert [f['media_kind'] for f in prepared['question_files']]==['document','image']
    publish_fixture(tmp_path,[row])
    assert load_file(sha256(text).hexdigest(),root=tmp_path)==(text,'text/plain')
    assert load_file(sha256(PNG).hexdigest(),root=tmp_path)==(PNG,'image/png')
    assert load_file('e'*64,root=tmp_path) is None and load_file('../file',root=tmp_path) is None
    assert add_files([{**row,'question_files':[{'sha256':'fake'}]}],root=tmp_path)==[prepared]


@pytest.mark.parametrize('change',['thread','question','message','saved','ambiguous','no_image','document_marker'])
def test_files_cannot_bind_to_another_question_or_unverified_attachment(tmp_path,change):
    media='document' if change=='document_marker' else 'image';archive_file(b'# text' if media=='document' else PNG,observation(media),root=tmp_path)
    row=original();rows=[row]
    if change=='thread':row['sources'][0]['thread_id']=MESSAGE
    elif change=='question':row['question']='另一个问题'
    elif change=='message':row['sources'][0]['turn_id']=THREAD
    elif change=='saved':row['kind']='saved_research'
    elif change=='ambiguous':rows.append(deepcopy(row))
    elif change=='no_image':row['unavailable_attachments']=0
    assert all('question_files' not in r for r in add_files(rows,root=tmp_path))


@pytest.mark.parametrize('change',['foreign_host','wrong_message','future','naive','path','html_type','binary_text','multiple','missing_provenance'])
def test_archive_rejects_unbound_or_unsafe_file_metadata(tmp_path,change):
    o=observation('document');raw=b'# safe'
    if change=='foreign_host':o['source_url']='https://example.test/c/'+THREAD
    elif change=='wrong_message':o['source_message_id']=THREAD
    elif change=='future':o['observed_at']='2099-01-01T00:00:00Z'
    elif change=='naive':o['observed_at']='2026-06-03T00:00:00'
    elif change=='path':o['file_name']='../other.md'
    elif change=='html_type':o['file_name']='page.html'
    elif change=='binary_text':raw=b'\xff\x00'
    elif change=='multiple':o['attachment_count']=2
    else:o['binding_record_sha256']=''
    with pytest.raises((ValueError,UnicodeError)):archive_file(raw,o,root=tmp_path)
    assert not (tmp_path/'files/assets').exists()


def test_changed_file_withdraws_the_old_review_and_corrupt_or_symlinked_bytes_are_not_served(tmp_path):
    from test_research_history import sample
    row=original();archive_file(PNG,observation(),root=tmp_path);prepared=add_files([row],root=tmp_path)[0];paths,_=sample()
    old=freeze_review({'question_digest':question_digest(prepared),'then_quote':'更像洗盘','headline':'原复盘'},prepared,paths,'2026-06-02')
    archive_file(PNG+b'new version',{**observation(),'observed_at':'2026-06-04T00:00:00Z'},root=tmp_path)
    changed=add_files([row],root=tmp_path)[0];state=assemble([changed],paths,reviews={row['id']:old})['details']['002514.SZ']['questions'][0]
    assert state['review'] is None and state['previous_review']==old
    publish_fixture(tmp_path,[row]);identity=changed['question_files'][0]['sha256'];asset=tmp_path/'files/assets'/(identity+'.png');asset.write_bytes(b'corrupt')
    assert load_file(identity,root=tmp_path) is None
    outside=tmp_path/'outside.png';outside.write_bytes(PNG+b'new version');asset.unlink();asset.symlink_to(outside)
    assert load_file(identity,root=tmp_path) is None


def test_file_api_is_read_only_plain_text_and_never_routes_an_arbitrary_file(monkeypatch):
    from fastapi.testclient import TestClient
    from api import app
    import research_history
    raw=b'<script>original text only</script>';identity=sha256(raw).hexdigest()
    monkeypatch.setattr(research_history,'load_file',lambda key:(raw,'text/plain') if key==identity else None)
    client=TestClient(app);url='/api/v1/workbench/history-files/'+identity;r=client.get(url)
    assert r.status_code==200 and r.content==raw and r.headers['content-type'].startswith('text/plain')
    assert r.headers['cache-control']=='private, no-store' and r.headers['x-content-type-options']=='nosniff'
    assert client.get('/api/v1/workbench/history-files/'+'a'*64).status_code==404
    assert client.get('/api/v1/workbench/history-files/invalid').status_code==422 and client.post(url).status_code==405
