"""Bind a written retrospective to its assessed prices, not future observations."""
import re

from canonical_json import digest

VERSION='history_review_window_v1'


def validate_quote(review,record):
    clean=lambda text:re.sub(r'[\s*_>#`]','',text)
    quote=clean(review['then_quote'])
    if not quote or quote not in clean(' '.join(a['text'] for a in record['answers'])):
        raise ValueError('review quote is not in original answer')


def window_digest(paths,scope,anchor,through):
    calendar=paths['calendar']
    if not anchor or anchor not in calendar or through not in calendar or anchor>through:
        raise ValueError('review window is outside available calendar')
    days=[day for day in calendar if anchor<=day<=through]
    if days!=sorted(set(days)):raise ValueError('review calendar is not unique and ordered')
    def section(points):
        selected=[{k:p[k] for k in ('date','value','level','basis') if k in p} for p in points if anchor<=p['date']<=through]
        if [p['date'] for p in selected]!=days:raise ValueError('review price window has missing or duplicate rows')
        return selected
    try:
        stocks={symbol:section(paths['stocks'][symbol]['points']) for symbol in scope}
    except KeyError as exc:raise ValueError('review scoped stock is missing') from exc
    return digest({'calendar':days,'stocks':stocks,'market':section(paths['market']),'st':section(paths['st']),
                   'st_name':paths['st_name'],'st_source_url':paths['st_source_url']})


def freeze_review(review,record,paths,anchor,*,through=None):
    """Call only after checking the old binding or writing a new substantive review."""
    validate_quote(review,record)
    scope=sorted(set(record['symbols']))
    focus=review.get('focused_symbol') or (scope[0] if len(scope)==1 else 'market' if not scope else None)
    if focus not in (scope or ['market']):raise ValueError('review needs an explicit related focused stock')
    through=through or paths['calendar'][-1]
    return {**review,'review_binding_version':VERSION,'price_through':through,'scope_symbols':scope,
            'focused_symbol':focus,'anchor_date':anchor,'price_window_digest':window_digest(paths,scope,anchor,through)}


def resolve_review(review,record,paths,question_digest,anchor):
    if not review:return {'review':None,'review_status':'not_reviewed'}
    if review.get('question_digest')!=question_digest:
        return {'review':None,'previous_review':review,'review_status':'original_changed'}
    # A changed price must never conceal a fabricated quote in an unchanged answer.
    validate_quote(review,record)
    if not review.get('review_binding_version'):
        matches=review.get('price_digest')==digest(paths)
    else:
        matches=False
        if (review['review_binding_version']==VERSION and review.get('scope_symbols')==sorted(set(record['symbols']))
                and review.get('anchor_date')==anchor and review.get('focused_symbol') in (record['symbols'] or ['market'])):
            try:matches=review.get('price_window_digest')==window_digest(paths,review['scope_symbols'],anchor,review['price_through'])
            except (ValueError,KeyError,TypeError):pass
    if not matches:return {'review':None,'previous_review':review,'review_status':'price_changed'}
    status='new_observations' if review.get('price_through',paths['calendar'][-1])<paths['calendar'][-1] else 'current'
    return {'review':review,'review_status':status}
