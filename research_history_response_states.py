"""Exact original-turn stop observations, separate from missing or later answers."""
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from canonical_json import digest

VERSION = 'history_original_response_state_v2'
OBSERVATION = 'history_response_stop_observation_v1'
UUID = re.compile(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}')
SHA = re.compile(r'[a-f0-9]{64}')
LABEL = re.compile(r'Stopped thinking|Stopped after [1-9][0-9]{0,2} (?:seconds?|minutes?|hours?)')


def validate_observation(value):
    thread = value['source_thread_id']; identity = value['question_id']
    if (value['version'] != OBSERVATION or not UUID.fullmatch(thread)
            or not identity.startswith('QUESTION-') or not UUID.fullmatch(identity[9:])):
        raise ValueError('stop observation identity changed')
    url = urlsplit(value['observed_url'])
    if (url.scheme != 'https' or url.netloc != 'chatgpt.com'
            or not url.path.endswith('/c/' + thread) or url.query or url.fragment):
        raise ValueError('stop observation conversation changed')
    stamp = datetime.fromisoformat(value['observed_at'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
        raise ValueError('invalid stop observation time')
    question, label, excerpt = value['question'], value['observed_label'], value['dialogue_excerpt']
    if not question.strip() or not LABEL.fullmatch(label):
        raise ValueError('only an explicit stopped label establishes a stopped response')
    prefix = question + '\n' + label + '\n'
    if (not excerpt.startswith(prefix) or '\nYou said:\n' not in excerpt
            or 'ChatGPT said:' in excerpt.split('\nYou said:\n', 1)[0]):
        raise ValueError('stop label must directly follow this original before the next question')


def freeze_stopped_response(record, observation, *, capture_sha256, tool_call_id):
    from research_history import question_digest
    validate_observation(observation)
    state = {'version': VERSION, 'status': 'response_stopped', 'question_id': record['id'],
             'question_digest': question_digest(record), 'source_url': 'https://chatgpt.com/c/' + observation['source_thread_id'],
             'observed_label': observation['observed_label'], 'capture_sha256': capture_sha256,
             'tool_call_id': tool_call_id, 'observation': observation, 'observation_digest': digest(observation)}
    if project_stopped_response(state, record) is None:
        raise ValueError('stopped response must bind its exact unanswered source turn')
    return state


def project_stopped_response(state, record):
    from research_history import question_digest
    try:
        observation = state['observation']; validate_observation(observation)
        if (state['version'] != VERSION or state['status'] != 'response_stopped'
                or record['kind'] != 'original_question' or record['answers']
                or state['question_id'] != record['id'] or observation['question_id'] != record['id']
                or observation['question'] != record['question'] or state['question_digest'] != question_digest(record)
                or state['observation_digest'] != digest(observation)
                or state['observed_label'] != observation['observed_label']
                or not SHA.fullmatch(state['capture_sha256'])
                or not isinstance(state['tool_call_id'], str) or not 0 < len(state['tool_call_id']) <= 200
                or state['source_url'] != 'https://chatgpt.com/c/' + observation['source_thread_id']
                or not any(s.get('kind') in {'chatgpt', 'chatgpt_rendered'}
                           and s.get('thread_id') == observation['source_thread_id']
                           and s.get('turn_id') == record['id'][9:] and s.get('url') == state['source_url']
                           for s in record['sources'])):
            return None
        return {k: state[k] for k in ('version', 'status', 'source_url', 'observed_label')}
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
