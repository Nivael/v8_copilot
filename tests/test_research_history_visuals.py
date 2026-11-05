import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from research_history import assemble,load_visual,prepare_history_records,publish,question_digest
from research_history_reviews import freeze_review
from research_history_visuals import PREFIX,add_visuals,collect_capture,image_info
from test_research_history import sample

THREAD='11111111-1111-4111-8111-111111111111'
MESSAGE='22222222-2222-4222-8222-222222222222'
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')


def observation():
    return {'version':'history_attachment_observation_v1','source_url':'https://chatgpt.com/c/'+THREAD,
            'question_id':'QUESTION-'+MESSAGE,'question':'看一下这张图','source_message_id':MESSAGE,
            'kind':'rendered_capture','observed_at':'2026-06-03T00:00:00Z',
            'image':{'natural_width':2,'natural_height':2,'src':'blob:https://chatgpt.com/local'},
            'capture':{'x':10,'y':10,'width':1,'height':1},'note':'原附件展示截图'}


def tool_log(tmp_path,value=None,raw=PNG,*,namespace='mcp__cua_repl',extra_image=False):
    text=PREFIX+json.dumps(value or observation(),ensure_ascii=False,separators=(',',':'))
    output=[{'type':'input_text','text':text},{'type':'input_image','image_url':'data:image/png;base64,'+base64.b64encode(raw).decode()}]
    if extra_image:output.append(output[-1])
    log=tmp_path/'selected-log.jsonl'
    log.write_text('\n'.join(json.dumps(e) for e in [
        {'type':'response_item','payload':{'type':'function_call','call_id':'capture-call','namespace':namespace,'name':'js'}},
        {'type':'response_item','payload':{'type':'function_call_output','call_id':'capture-call','output':output}}]))
    return log


def original():
    _,row=sample();row.update(id='QUESTION-'+MESSAGE,question=observation()['question'],unavailable_attachments=1,
                             sources=[{'kind':'chatgpt_rendered','thread_id':THREAD,'turn_id':MESSAGE}])
    return row


def captured(tmp_path):
    return collect_capture(tool_log(tmp_path),'capture-call',root=tmp_path)


def publish_fixture(tmp_path,records):
    import research_history_prices
    paths,_=sample();packet={'data':paths,'processor_digest':sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest()}
    packet['content_digest']=digest(packet);atomic_write_json(tmp_path/'price_paths/current.json',packet)
    return publish({'records':records,'sources':[]},root=tmp_path)


def test_only_selected_cua_returned_image_is_archived_and_replayed_without_original_file_claim(tmp_path):
    wrapper=captured(tmp_path);row=original();before=deepcopy(row)
    prepared=add_visuals([row],root=tmp_path)[0];visual=prepared['question_visuals'][0]
    assert row==before and prepared['unavailable_attachments']==1
    assert visual['kind']=='rendered_capture' and visual['sha256']==sha256(PNG).hexdigest()
    assert visual['source_message_id']==MESSAGE and visual['source_url']=='https://chatgpt.com/c/'+THREAD
    assert (tmp_path/'visuals/assets'/(visual['sha256']+'.png')).read_bytes()==PNG
    assert wrapper['original_output'].startswith(PREFIX) and wrapper['tool_call_id']=='capture-call'
    assert collect_capture(tool_log(tmp_path),'capture-call',root=tmp_path)['content_digest']==wrapper['content_digest']
    assert len(list((tmp_path/'visuals/captures').glob('*.json')))==1


@pytest.mark.parametrize('change',['wrong_tool','extra_image','not_image','wrong_size','foreign_host','wrong_message','future','naive_time'])
def test_collector_rejects_unbound_or_misdescribed_images(tmp_path,change):
    value=observation();kwargs={}
    if change=='wrong_tool':kwargs['namespace']='another_tool'
    elif change=='extra_image':kwargs['extra_image']=True
    elif change=='not_image':kwargs['raw']=b'<svg>not a permitted capture</svg>'
    elif change=='wrong_size':value['capture']['width']=2
    elif change=='foreign_host':value['source_url']='https://example.test/c/'+THREAD
    elif change=='wrong_message':value['source_message_id']=THREAD
    elif change=='future':value['observed_at']='2099-01-01T00:00:00Z'
    else:value['observed_at']='2026-06-03T00:00:00'
    with pytest.raises(ValueError):collect_capture(tool_log(tmp_path,value,**kwargs),'capture-call',root=tmp_path)
    assert not (tmp_path/'visuals/assets').exists()


@pytest.mark.parametrize('change',['question','thread','message','multi_image','no_image','ambiguous','saved'])
def test_visible_image_cannot_be_attached_to_a_different_or_ambiguous_canonical_question(tmp_path,change):
    captured(tmp_path);rows=[original()];row=rows[0]
    if change=='question':row['question']='后来纠正过的原问题'
    elif change=='thread':row['sources'][0]['thread_id']=MESSAGE
    elif change=='message':row['sources'][0]['turn_id']=THREAD
    elif change=='multi_image':row['unavailable_attachments']=2
    elif change=='no_image':row['unavailable_attachments']=0
    elif change=='ambiguous':rows.append(deepcopy(row))
    else:row['kind']='saved_research'
    assert all('question_visuals' not in r for r in add_visuals(rows,root=tmp_path))


def test_import_annotations_are_ignored_and_changed_visual_withdraws_assessment_without_redating_it(tmp_path):
    row=original();paths,_=sample();old=freeze_review({'question_digest':question_digest(row),'then_quote':'更像洗盘','headline':'原复盘'},row,paths,'2026-06-02')
    row['question_visuals']=[{'kind':'original_file','url':'https://unverified.test/image'}]
    assert 'question_visuals' not in prepare_history_records({'records':[row]},root=tmp_path)[0]
    captured(tmp_path);prepared=prepare_history_records({'records':[row]},root=tmp_path)[0]
    result=assemble([prepared],paths,reviews={row['id']:old})['details']['002514.SZ']['questions'][0]
    assert result['review'] is None and result['previous_review']==old and result['review_status']=='original_changed'
    after=deepcopy(prepared);after['question_visuals'][0].update(captured_at='2026-06-04T00:00:00Z',capture_digest='new-provenance-only')
    assert question_digest(after)==question_digest(prepared)
    after['question_visuals'][0]['sha256']='a'*64
    assert question_digest(after)!=question_digest(prepared)


def test_only_published_current_hash_checked_bytes_are_served_and_corruption_fails_closed(tmp_path):
    wrapper=captured(tmp_path);identity=wrapper['asset']['sha256']
    assert load_visual(identity,root=tmp_path) is None
    packet=publish_fixture(tmp_path,[original()])
    assert load_visual(identity,root=tmp_path)==(PNG,'image/png')
    assert load_visual('a'*64,root=tmp_path) is None and load_visual('../outside',root=tmp_path) is None
    asset_path=tmp_path/'visuals/assets'/(identity+'.png');asset_path.write_bytes(PNG+b'changed')
    assert load_visual(identity,root=tmp_path) is None
    with pytest.raises(ValueError,match='bytes changed'):publish_fixture(tmp_path,[original()])
    asset_path.write_bytes(PNG)
    packet['processor_digest']='old';packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'});atomic_write_json(tmp_path/'current.json',packet)
    assert load_visual(identity,root=tmp_path) is None


def test_a_different_valid_capture_revision_needs_a_fresh_review(tmp_path):
    captured(tmp_path);row=add_visuals([original()],root=tmp_path)[0];paths,_=sample()
    review=freeze_review({'question_digest':question_digest(row),'then_quote':'更像洗盘','headline':'已读附图'},row,paths,'2026-06-02')
    new=observation();new['observed_at']='2026-06-04T00:00:00Z'
    collect_capture(tool_log(tmp_path,new,PNG+b'another valid image revision'),'capture-call',root=tmp_path)
    changed=add_visuals([row],root=tmp_path)[0]
    assert changed['question_visuals'][0]['sha256']!=row['question_visuals'][0]['sha256']
    state=assemble([changed],paths,reviews={row['id']:review})['details']['002514.SZ']['questions'][0]
    assert state['review'] is None and state['previous_review']==review


def test_asset_api_is_read_only_and_returns_only_verified_bytes(monkeypatch):
    from fastapi.testclient import TestClient
    from api import app
    import research_history
    identity=sha256(PNG).hexdigest()
    monkeypatch.setattr(research_history,'load_visual',lambda key:(PNG,'image/png') if key==identity else None)
    client=TestClient(app);url='/api/v1/workbench/history-assets/'+identity
    response=client.get(url)
    assert response.status_code==200 and response.content==PNG and response.headers['content-type']=='image/png'
    assert response.headers['cache-control']=='private, no-store' and response.headers['x-content-type-options']=='nosniff'
    assert client.get('/api/v1/workbench/history-assets/'+'a'*64).status_code==404
    assert client.get('/api/v1/workbench/history-assets/invalid').status_code==422
    assert client.post(url).status_code==405


def test_image_limit_rejects_excessive_dimensions_and_non_image_content():
    raw=bytearray(PNG);raw[16:20]=(10000).to_bytes(4,'big')
    with pytest.raises(ValueError,match='dimensions'):image_info(bytes(raw))
    with pytest.raises(ValueError):image_info(b'<html>not image</html>')
