"""Source-bound, precomputed event context for a historical question.

This is a read model, not a new announcement classifier or causal lens. It keeps
the original question reference separate from each disclosure-day price window.
"""
from datetime import date
from urllib.parse import urlsplit
import re

from canonical_json import digest
from event_learning import audit_events, following_windows

VERSION = 'history_event_timeline_v1'
LENSES = {'RL-C-001', 'RL-C-002', 'RL-C-003', 'RL-C-004'}


def _day(value):
    return date.fromisoformat(value).isoformat()


def build_timeline(*, question_id, question_digest, asked_on, symbol, review_window_digest, experience_id,
                   paths, source_run_id, source_pack_id, events, annotations, sources,
                   initial_event_id):
    """Only explicitly annotated, audited events can enter the reading model."""
    audit_events(events)
    if not events or set(annotations) != {e['id'] for e in events}:
        raise ValueError('event annotations must match the complete selected event set')
    _day(asked_on)
    if (symbol not in paths['stocks'] or not source_run_id or not source_pack_id
            or not re.fullmatch(r'EXP-[0-9A-F]{20}', experience_id)):
        raise ValueError('event timeline needs its company and research binding')
    rows = []
    for event in events:
        note = annotations[event['id']]
        if any(not isinstance(note.get(k), str) or not note[k].strip()
               for k in ['title', 'change', 'interpretation', 'watch']):
            raise ValueError('event needs a readable change, interpretation and next condition')
        if not note.get('lens_ids') or not set(note['lens_ids']) <= LENSES:
            raise ValueError('event lens must be an actual released methodology')
        source = sources[event['id']]
        parsed = urlsplit(source['url'])
        if (parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password
                or not re.fullmatch(r'[0-9]{10}', source['announcement_id'])
                or source['announcement_id'] != event['source_id']
                or source['published_on'] != event['published_on']
                or not re.fullmatch(r'[0-9a-f]{64}', source['sha256'])
                or type(note.get('page')) is not int or not 1 <= note['page'] <= source['pages']):
            raise ValueError('event primary source identity, disclosure date or page differs')
        relation = ('before_question' if event['published_on'] < asked_on else
                    'same_day' if event['published_on'] == asked_on else 'after_question')
        context = following_windows(paths['stocks'][symbol]['points'], paths['market'], paths['st'],
                                    paths['calendar'], event['published_on'], counts=(1, 5, 20))
        rows.append({
            'id': event['id'], 'published_on': event['published_on'],
            'occurred_on': event.get('occurred_on') if event['state_after'] != 'scheduled' else None,
            'scheduled_for': event.get('occurred_on') if event['state_after'] == 'scheduled' else None,
            'publication_precision': 'day',
            'relation': relation, 'entity_scope': event['entity_scope'],
            'change_kind': event['change_kind'], 'title': note['title'], 'change': note['change'],
            'interpretation': note['interpretation'], 'watch': note['watch'],
            'lens_ids': list(note['lens_ids']), 'highlight': note.get('highlight') is True,
            'source': {'announcement_id': source['announcement_id'], 'title': source['title'],
                       'url': source['url'] + f"#page={note['page']}", 'page': note['page'],
                       'sha256': source['sha256']}, 'context': context,
        })
    if initial_event_id not in annotations:
        raise ValueError('initial event must belong to this timeline')
    payload = {'version': VERSION, 'question_id': question_id, 'question_digest': question_digest,
               'asked_on': asked_on, 'symbol': symbol, 'review_window_digest': review_window_digest,
               'price_data_digest': digest(paths), 'source_run_id': source_run_id,
               'source_pack_id': source_pack_id, 'source_events_digest': digest(events),
               'initial_event_id': initial_event_id, 'experience_id': experience_id, 'events': rows,
               'causal_effect_identified': False}
    return {**payload, 'content_digest': digest(payload)}


def project_timeline(value, *, record, review, paths, symbol):
    """Hide a stale or foreign timeline without altering the original review."""
    try:
        from research_history import question_day
        if (value['version'] != VERSION
                or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value['content_digest']
                or value['question_id'] != record['id']
                or value['asked_on'] != question_day(record)
                or value['question_digest'] != review['question_digest']
                or value['symbol'] != symbol or symbol != review['focused_symbol']
                or value['review_window_digest'] != review['price_window_digest']
                or value['price_data_digest'] != digest(paths)
                or value['source_run_id'] != review['learning_trace']['source_run_id']
                or value['source_pack_id'] != review['learning_trace']['source_pack_id']
                or value['experience_id'] != review['learning_trace']['experience_candidate_id']
                or value['causal_effect_identified'] is not False):
            return None
        ids = [e['id'] for e in value['events']]
        if not ids or len(ids) != len(set(ids)) or value['initial_event_id'] not in ids:
            return None
        for event in value['events']:
            expected = following_windows(paths['stocks'][symbol]['points'], paths['market'], paths['st'],
                                         paths['calendar'], event['published_on'], counts=(1, 5, 20))
            relation = ('before_question' if event['published_on'] < value['asked_on'] else
                        'same_day' if event['published_on'] == value['asked_on'] else 'after_question')
            if (event['context'] != expected or event['publication_precision'] != 'day'
                    or event['relation'] != relation
                    or event.get('occurred_on') and event['occurred_on'] > event['published_on']):
                return None
        return value
    except (KeyError, TypeError, ValueError):
        return None
