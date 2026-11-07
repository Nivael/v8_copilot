"""Source-bound, precomputed event context for a historical question.

This is a read model, not a new announcement classifier or causal lens. It keeps
the original question reference separate from each disclosure-day price window.
"""
from datetime import date
from copy import deepcopy
from urllib.parse import urlsplit
import re

from canonical_json import digest
from event_learning import audit_events, following_windows

VERSION = 'history_event_timeline_v1'
LENSES = {'RL-C-001', 'RL-C-002', 'RL-C-003', 'RL-C-004'}
ARGUMENT_VERSION = 'history_event_timeline_v2'
CASE_VERSION = 'history_event_timeline_v3'
QUESTION_VERSION = 'history_event_timeline_v4'


def _day(value):
    return date.fromisoformat(value).isoformat()


def _event_rows(*, asked_on, symbol, paths, events, annotations, sources, case_paths=None):
    audit_events(events)
    if not events or set(annotations) != {e['id'] for e in events}:
        raise ValueError('event annotations must match the complete selected event set')
    _day(asked_on)
    if symbol not in paths['stocks']:
        raise ValueError('event timeline needs its company')
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
        selected_paths = _event_paths(paths, case_paths, event['published_on'])
        context = following_windows(selected_paths['stocks'][symbol]['points'], selected_paths['market'], selected_paths['st'],
                                    selected_paths['calendar'], event['published_on'], counts=(1, 5, 20))
        if event.get('symbol', symbol) != symbol:
            raise ValueError('event belongs to another company')
        extra = {}
        for key, allowed in [('occurred_date_qualifier', {'local_time'}), ('scheduled_role', {'warning_effective_date'})]:
            if key in note:
                if note[key] not in allowed:
                    raise ValueError('unknown event date role')
                extra[key] = note[key]
        if 'price_note' in note:
            if not isinstance(note['price_note'], str) or not note['price_note'].strip():
                raise ValueError('empty event price note')
            extra['price_note'] = note['price_note']
        rows.append({**extra, **({'context_period': 'case_period' if selected_paths is case_paths else 'question_period'} if case_paths else {}),
            'id': event['id'], 'published_on': event['published_on'],
            'occurred_on': event.get('occurred_on') if event['state_after'] != 'scheduled' and note.get('date_role') != 'report_period_end' else None,
            'scheduled_for': event.get('occurred_on') if event['state_after'] == 'scheduled' else None,
            'report_period_end': event.get('occurred_on') if note.get('date_role') == 'report_period_end' else None,
            'publication_precision': 'day',
            'relation': relation, 'entity_scope': event['entity_scope'],
            'change_kind': event['change_kind'], 'title': note['title'], 'change': note['change'],
            'evidence_detail': event['fact'],
            'interpretation': note['interpretation'], 'watch': note['watch'],
            'lens_ids': list(note['lens_ids']), 'highlight': note.get('highlight') is True,
            'source': {'announcement_id': source['announcement_id'], 'title': source['title'],
                       'url': source['url'] + f"#page={note['page']}", 'page': note['page'],
                       'sha256': source['sha256']}, 'context': context,
        })
    return rows


def _event_paths(paths, case_paths, day):
    return case_paths if case_paths and case_paths['calendar'][0] <= day <= case_paths['calendar'][-1] else paths


def build_timeline(*, question_id, question_digest, asked_on, symbol, review_window_digest, experience_id,
                   paths, source_run_id, source_pack_id, events, annotations, sources,
                   initial_event_id):
    """Only explicitly annotated, audited events can enter the reading model."""
    if not source_run_id or not source_pack_id or not re.fullmatch(r'EXP-[0-9A-F]{20}', experience_id):
        raise ValueError('event timeline needs its research binding')
    rows = _event_rows(asked_on=asked_on, symbol=symbol, paths=paths, events=events, annotations=annotations, sources=sources)
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


def _reading_digest(rows):
    return digest([{k: v for k, v in row.items() if k != 'context'} for row in rows])


def _argument_basis(review):
    return digest({k: v for k, v in review.items() if k != 'event_timelines'})


def freeze_argument_timelines(review, *, record, paths, source_run_id, source_pack_id,
                              events, annotations, sources, applied_lens_ids, learning, case_periods=None, question_periods=None):
    """Bind company event context without turning an argument into a trade review.

    The caller supplies a validated historical study and its actual applied lenses.
    No experience is created or promoted by this read-model operation.
    """
    from research_history import question_day, question_digest
    from research_history_reviews import argument_binding_matches
    if (not argument_binding_matches(review, record) or review['question_digest'] != question_digest(record)
            or not re.fullmatch(r'RUN-[A-F0-9]{24}', source_run_id)
            or not source_pack_id or not applied_lens_ids or not set(applied_lens_ids) <= LENSES):
        raise ValueError('argument event context needs an exact original and actual study')
    if not isinstance(learning, dict) or set(learning) != {'lesson', 'next_check'} or any(
            not isinstance(v, str) or not v.strip() for v in learning.values()):
        raise ValueError('event context needs conditional learning and a next check')
    audit_events(events)
    if not events or set(annotations) != {e['id'] for e in events}:
        raise ValueError('selected event annotations differ')
    symbols = sorted({e['symbol'] for e in events})
    case_periods = deepcopy(case_periods or {})
    question_periods = deepcopy(question_periods or {})
    if set(question_periods) & set(case_periods) or not set(question_periods) <= set(symbols):
        raise ValueError('question and past-case periods must remain separate')
    if not set(case_periods) <= set(symbols):
        raise ValueError('case period belongs to another event subject')
    if not set(symbols) <= set(record['symbols']):
        raise ValueError('event subjects differ from the original scope')
    rows_by_symbol = {}
    traces = {}
    asked_on = question_day(record)
    for symbol in symbols:
        period = case_periods.get(symbol)
        if period is not None:
            from research_history_case_period import case_period_paths
            case_paths = case_period_paths(period, symbol=symbol, asked_on=asked_on, current_start=paths['calendar'][0])
        else:
            case_paths = None
        question_period = question_periods.get(symbol)
        if question_period is not None:
            from research_history_question_period import question_period_paths
            selected_paths = question_period_paths(question_period, symbol=symbol, asked_on=asked_on)
        else:
            selected_paths = paths
        selected = [e for e in events if e['symbol'] == symbol]
        rows = _event_rows(asked_on=asked_on, symbol=symbol, paths=selected_paths, events=selected,
                           annotations={e['id']: annotations[e['id']] for e in selected}, sources=sources, case_paths=case_paths)
        if not {lens for row in rows for lens in row['lens_ids']} <= set(applied_lens_ids):
            raise ValueError('event reading cites a lens absent from the actual study')
        rows_by_symbol[symbol] = rows
        traces[symbol] = {'source_events_digest': digest(selected), 'reading_digest': _reading_digest(rows)}
        if period is not None:
            traces[symbol]['case_period_digest'] = period['content_digest']
        if question_period is not None:
            traces[symbol]['question_period_digest'] = question_period['content_digest']
    trace = {'source_run_id': source_run_id, 'source_pack_id': source_pack_id,
             'source_events_digest': digest(events), 'applied_lens_ids': list(applied_lens_ids),
             'subjects': traces, 'learning': dict(learning)}
    result = {**review, 'event_trace': trace}
    timelines = {}
    for symbol, rows in rows_by_symbol.items():
        period = case_periods.get(symbol)
        question_period = question_periods.get(symbol)
        payload = {'version': QUESTION_VERSION if question_period is not None else CASE_VERSION if period is not None else ARGUMENT_VERSION, 'assessment_basis': 'original_argument_only',
                   'question_id': record['id'], 'question_digest': question_digest(record),
                   'asked_on': asked_on, 'symbol': symbol, 'review_basis_digest': _argument_basis(result),
                   'price_data_digest': digest(paths), 'source_run_id': source_run_id,
                   'source_pack_id': source_pack_id, 'source_events_digest': traces[symbol]['source_events_digest'],
                   'reading_digest': traces[symbol]['reading_digest'], 'learning': dict(learning),
                   'initial_event_id': next((e['id'] for e in rows if e['relation'] != 'before_question'), rows[-1]['id']),
                   'events': rows, 'causal_effect_identified': False}
        if period is not None:
            payload['case_period'] = period
        if question_period is not None:
            payload['question_period'] = question_period
        timelines[symbol] = {**payload, 'content_digest': digest(payload)}
    return {**result, 'event_timelines': timelines}


def project_argument_timeline(value, *, record, review, paths, symbol):
    """Validate original, scope, study, authored reading and prices independently."""
    from research_history import question_day, question_digest
    from research_history_reviews import argument_binding_matches
    try:
        trace = review['event_trace']
        subject = trace['subjects'][symbol]
        if (not argument_binding_matches(review, record) or symbol not in record['symbols']
                or value['version'] not in {ARGUMENT_VERSION, CASE_VERSION, QUESTION_VERSION}
                or value['assessment_basis'] != 'original_argument_only'
                or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value['content_digest']
                or value['review_basis_digest'] != _argument_basis(review)
                or value['question_id'] != record['id'] or value['symbol'] != symbol
                or value['question_digest'] != question_digest(record)
                or value['asked_on'] != question_day(record)
                or value['price_data_digest'] != digest(paths)
                or any(value[k] != trace[k] for k in ('source_run_id', 'source_pack_id', 'learning'))
                or value['source_events_digest'] != subject['source_events_digest']
                or value['reading_digest'] != subject['reading_digest']
                or _reading_digest(value['events']) != subject['reading_digest']
                or value['causal_effect_identified'] is not False
                or 'experience_id' in value):
            return None
        if value['version'] == CASE_VERSION:
            from research_history_case_period import case_period_paths
            period = value['case_period']
            if period['content_digest'] != subject['case_period_digest']:
                return None
            case_paths = case_period_paths(period, symbol=symbol, asked_on=value['asked_on'], current_start=paths['calendar'][0])
        else:
            if 'case_period' in value or 'case_period_digest' in subject:
                return None
            case_paths = None
        question_paths = paths
        if value['version'] == QUESTION_VERSION:
            from research_history_question_period import question_period_paths
            period = value['question_period']
            if period['content_digest'] != subject['question_period_digest']:
                return None
            question_paths = question_period_paths(period, symbol=symbol, asked_on=value['asked_on'])
        elif 'question_period' in value or 'question_period_digest' in subject:
            return None
        ids = [e['id'] for e in value['events']]
        if not ids or len(ids) != len(set(ids)) or value['initial_event_id'] not in ids:
            return None
        for event in value['events']:
            selected_paths = _event_paths(question_paths, case_paths, event['published_on'])
            relation = ('before_question' if event['published_on'] < value['asked_on'] else
                        'same_day' if event['published_on'] == value['asked_on'] else 'after_question')
            if (not set(event['lens_ids']) <= set(trace['applied_lens_ids'])
                    or event['publication_precision'] != 'day' or event['relation'] != relation
                    or (event.get('context_period') != ('case_period' if selected_paths is case_paths else 'question_period') if case_paths else 'context_period' in event)
                    or event['context'] != following_windows(selected_paths['stocks'][symbol]['points'], selected_paths['market'],
                            selected_paths['st'], selected_paths['calendar'], event['published_on'], counts=(1, 5, 20))):
                return None
        return value
    except (KeyError, TypeError, ValueError):
        return None


def project_review_events(review, *, record, paths, symbol):
    """Return only this company's projection, never all maps on every group view."""
    result = {k: v for k, v in review.items() if k not in {'event_timeline', 'event_timelines'}}
    if 'event_timelines' in review:
        value = review['event_timelines'].get(symbol)
        projected = project_argument_timeline(value, record=record, review=review, paths=paths, symbol=symbol) if value else None
    elif 'event_timeline' in review:
        value = review['event_timeline']
        projected = project_timeline(value, record=record, review=review, paths=paths, symbol=symbol)
    else:
        return result
    if projected:
        result['event_timeline'] = projected
    elif value:
        result['event_timeline_status'] = 'needs_refresh'
    return result
