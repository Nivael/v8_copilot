"""Source-bound market context and same-conversation links for old macro questions."""
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode
import re

from canonical_json import digest

PERIOD_VERSION = 'history_market_period_sources_v1'
VERSION = 'history_argument_market_context_v1'


def market_period_paths(value, *, asked_on):
    if (not isinstance(value, dict) or value.get('version') != PERIOD_VERSION
            or value.get('price_basis') != 'market_and_st_price_only'
            or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value.get('content_digest')):
        raise ValueError('market period source binding changed')
    if any(not isinstance(value.get(k), str) or not value[k].strip() for k in ('title', 'summary', 'source_note')):
        raise ValueError('market period needs readable context')
    paths = value['paths']; calendar = paths['calendar']
    if (set(paths) != {'calendar', 'market', 'st', 'st_name'} or not 2 <= len(calendar) <= 640
            or calendar != sorted(set(calendar)) or any(date.fromisoformat(d).isoformat() != d for d in calendar)
            or not calendar[0] < asked_on <= calendar[-1] or paths['st_name'] != 'ST板块（东财）'):
        raise ValueError('market context must cover its original without inventing company prices')
    for points in (paths['market'], paths['st']):
        if [p['date'] for p in points] != calendar:
            raise ValueError('market series calendars differ')
        anchor = points[0]['value']
        for point in points:
            price, level = point['value'], point['level']
            if (any(type(v) not in {int, float} or not Decimal(str(v)).is_finite() or v <= 0 for v in (anchor, price, level))
                    or abs(Decimal(str(level)) - Decimal(str(price))/Decimal(str(anchor))*100) > Decimal('.00000001')):
                raise ValueError('market price or normalization changed')
    start, end = calendar[0], calendar[-1]
    expected = {
        'market': 'https://www.csindex.com.cn/csindex-home/perf/index-perf?' + urlencode({'indexCode': '000985', 'startDate': start.replace('-', ''), 'endDate': end.replace('-', '')}),
        'st': 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urlencode({'secid': '90.BK0511', 'klt': '101', 'fqt': '0', 'beg': start.replace('-', ''), 'end': end.replace('-', ''), 'fields1': 'f1,f2,f3,f4,f5,f6', 'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'}),
    }
    refs = value['source_refs']
    if len(refs) != 2 or {r['key'] for r in refs} != set(expected):
        raise ValueError('market source inventory differs')
    for ref in refs:
        stamp = datetime.fromisoformat(ref['observed_at'])
        if (ref['url'] != expected[ref['key']] or not re.fullmatch(r'[a-f0-9]{64}', ref['sha256'])
                or stamp.tzinfo is None or stamp > datetime.now(timezone.utc)
                or stamp.date().isoformat() < end or not ref.get('title')):
            raise ValueError('market source identity or observation time changed')
    return paths


def _shared_threads(record):
    return {(s['kind'], s['thread_id']) for s in record.get('sources', []) if s.get('thread_id')}


def _basis(review):
    return digest({k: v for k, v in review.items() if k != 'market_context'})


def freeze_market_context(review, *, record, period, related_records, source_run_id, source_pack_id):
    from research_history import question_day, question_digest
    from research_history_reviews import argument_binding_matches
    if (not argument_binding_matches(review, record) or review.get('question_digest') != question_digest(record)
            or record['symbols'] or review['focused_symbol'] != 'market'
            or not re.fullmatch(r'RUN-[A-F0-9]{24}', source_run_id) or not source_pack_id):
        raise ValueError('market argument context needs its exact original and actual study')
    market_period_paths(period, asked_on=question_day(record))
    related = {}
    for target in related_records:
        if (target['id'] == record['id'] or target['id'] in related or target['kind'] != 'original_question'
                or not _shared_threads(record) & _shared_threads(target)):
            raise ValueError('related questions must be distinct originals from the same source conversation')
        related[target['id']] = question_digest(target)
    trace = {'source_run_id': source_run_id, 'source_pack_id': source_pack_id,
             'period_digest': period['content_digest'], 'related_questions': related}
    result = {**review, 'market_context_trace': trace}
    payload = {'version': VERSION, 'question_id': record['id'], 'question_digest': question_digest(record),
               'review_basis_digest': _basis(result), 'period': deepcopy(period), **deepcopy(trace)}
    return {**result, 'market_context': {**payload, 'content_digest': digest(payload)}}


def project_market_context(review, *, record, records):
    from research_history import question_day, question_digest
    from research_history_reviews import argument_binding_matches
    try:
        value = review['market_context']; trace = review['market_context_trace']
        if (not argument_binding_matches(review, record) or record['symbols'] or review['focused_symbol'] != 'market'
                or value['version'] != VERSION or value['question_id'] != record['id']
                or value['question_digest'] != question_digest(record)
                or value['review_basis_digest'] != _basis(review)
                or digest({k: v for k, v in value.items() if k != 'content_digest'}) != value['content_digest']
                or any(value[k] != trace[k] for k in ('source_run_id', 'source_pack_id', 'period_digest', 'related_questions'))
                or value['period']['content_digest'] != trace['period_digest']):
            return None
        market_period_paths(value['period'], asked_on=question_day(record))
        for identity, expected in value['related_questions'].items():
            target = records[identity]
            if (identity == record['id'] or target['kind'] != 'original_question'
                    or question_digest(target) != expected or not _shared_threads(record) & _shared_threads(target)):
                return None
        return value
    except (KeyError, TypeError, ValueError):
        return None


def contexts_and_links(records, reviews, paths):
    """Project only verified links; company scope comes from the target original."""
    contexts = {}; links = {}; index = {r['id']: r for r in records}
    for record in records:
        review = reviews.get(record['id']) or {}
        if 'market_context' not in review:
            continue
        context = project_market_context(review, record=record, records=index)
        if context is None:
            continue
        contexts[record['id']] = context
        for identity in context['related_questions']:
            links.setdefault(record['id'], set()).add(identity)
            links.setdefault(identity, set()).add(record['id'])
    cards = {}
    for identity, targets in links.items():
        cards[identity] = []
        for target_id in sorted(targets):
            target = index[target_id]
            for symbol in target['symbols'] or ['market']:
                if symbol != 'market' and symbol not in paths['stocks']:
                    continue
                cards[identity].append({'question_id': target_id, 'symbol': symbol,
                    'name': paths['stocks'][symbol]['name'] if symbol != 'market' else '大盘与ST',
                    'question': target['question']})
    return contexts, cards
