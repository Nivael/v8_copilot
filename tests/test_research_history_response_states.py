from copy import deepcopy
import pytest

from canonical_json import digest
from research_history import assemble, original_response_state
from research_history_response_states import freeze_stopped_response, project_stopped_response
from test_research_history import sample


def fixture(label='Stopped thinking'):
    paths, record = sample()
    thread = '69fd671d-e4f8-83e9-a866-d554722708fc'
    message = '76c48902-1d49-49eb-9f9c-ddd19bff86bc'
    record.update(id='QUESTION-' + message, answers=[], sources=[{'kind': 'chatgpt', 'thread_id': thread,
                  'turn_id': message, 'url': 'https://chatgpt.com/c/' + thread}])
    observation = {'version': 'history_response_stop_observation_v1', 'source_thread_id': thread,
                   'question_id': record['id'], 'question': record['question'], 'observed_label': label,
                   'observed_at': '2026-10-01T00:00:00Z', 'observed_url': 'https://chatgpt.com/c/' + thread,
                   'dialogue_excerpt': record['question'] + '\n' + label + '\nYou said:\n补充后的另一次提问'}
    return paths, record, observation


@pytest.mark.parametrize('label', ['Stopped thinking', 'Stopped after 7 minutes'])
def test_explicit_stop_is_context_not_recovered_answer_or_completed_review(label):
    paths, record, observation = fixture(label)
    record['original_response_state'] = freeze_stopped_response(record, observation, capture_sha256='a'*64, tool_call_id='call_source')
    result = assemble([record], paths); question = result['details']['002514.SZ']['questions'][0]
    assert question['original_response_state']['observed_label'] == label
    assert question['original_response_state']['status'] == 'response_stopped'
    assert question['answers'] == [] and question['review'] is None and result['stocks'][0]['reviewed'] == 0
    assert 'observation' not in question['original_response_state']


@pytest.mark.parametrize('change', ['answer', 'question', 'kind', 'turn', 'thread', 'source_url', 'observation_question',
                                   'observation_identity', 'capture', 'tool', 'label', 'future', 'naive', 'url', 'digest',
                                   'completed_label', 'reply_before_stop', 'different_prefix'])
def test_changed_turn_source_or_non_stop_cannot_certify_an_unfinished_response(change):
    _, record, observation = fixture()
    state = freeze_stopped_response(record, observation, capture_sha256='a'*64, tool_call_id='call_source')
    state = deepcopy(state); observed = state['observation']
    if change == 'answer': record['answers'] = [{'text': '另一轮回答不能移到这里'}]
    elif change == 'question': record['question'] += '变动'
    elif change == 'kind': record['kind'] = 'saved_research'
    elif change == 'turn': record['sources'][0]['turn_id'] = 'other'
    elif change == 'thread': record['sources'][0]['thread_id'] = 'other'
    elif change == 'source_url': record['sources'][0]['url'] += '?other'
    elif change == 'observation_question': observed['question'] += '变动'
    elif change == 'observation_identity': observed['question_id'] = 'QUESTION-' + observed['source_thread_id']
    elif change == 'capture': state['capture_sha256'] = 'not-a-sha'
    elif change == 'tool': state['tool_call_id'] = ''
    elif change == 'label': state['observed_label'] = 'Research stopped'
    elif change == 'future': observed['observed_at'] = '2099-01-01T00:00:00Z'
    elif change == 'naive': observed['observed_at'] = '2026-10-01T00:00:00'
    elif change == 'url': observed['observed_url'] = 'https://example.com/c/' + observed['source_thread_id']
    elif change == 'digest': state['observation_digest'] = 'b'*64
    elif change == 'completed_label': observed['observed_label'] = 'Thought for 6m 3s'
    elif change == 'reply_before_stop': observed['dialogue_excerpt'] = observed['dialogue_excerpt'].replace('\nYou said:', '\nChatGPT said:\n真实答复\nYou said:')
    elif change == 'different_prefix': observed['dialogue_excerpt'] = '另一次提问\nStopped thinking\nYou said:\n再问'
    if change != 'digest': state['observation_digest'] = digest(observed)
    assert project_stopped_response(state, record) is None
    record['original_response_state'] = state
    assert original_response_state(record) is None


def test_project_path_is_allowed_but_not_a_different_conversation():
    _, record, observation = fixture()
    observation['observed_url'] = 'https://chatgpt.com/g/g-p-example-project/c/' + observation['source_thread_id']
    state = freeze_stopped_response(record, observation, capture_sha256='a'*64, tool_call_id='call_source')
    assert project_stopped_response(state, record)['source_url'] == record['sources'][0]['url']
    observation['observed_url'] += '-different'
    with pytest.raises(ValueError):
        freeze_stopped_response(record, observation, capture_sha256='a'*64, tool_call_id='call_source')
