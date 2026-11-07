"""Bind assessed price windows separately from original-argument-only reviews."""
import re

from canonical_json import digest

VERSION='history_review_window_v1'
ARGUMENT_VERSION='history_review_argument_v1'
ARGUMENT_BASIS='original_argument_only'
FOLLOWTHROUGH_VERSION='history_review_question_followthrough_v1'
FOLLOWTHROUGH_BASIS='question_followthrough'
PRICE_FIELDS={'price_digest','price_through','anchor_date','price_window_digest'}


def focus_options(record):
    scope=record['symbols']
    return [*scope,*(['market'] if not scope or record.get('market_scope') is True else [])]


def default_focus(record):
    scope=record['symbols']
    return 'market' if not scope or record.get('market_scope') is True else scope[0] if len(scope)==1 else None


def argument_review_claimed(review):
    return review.get('review_binding_version')==ARGUMENT_VERSION or review.get('assessment_basis')==ARGUMENT_BASIS


def argument_binding_matches(review,record):
    return (review.get('review_binding_version')==ARGUMENT_VERSION and review.get('assessment_basis')==ARGUMENT_BASIS
            and record['kind']=='original_question' and review.get('original_record_id')==record['id']
            and review.get('scope_symbols')==sorted(set(record['symbols']))
            and review.get('focused_symbol') in focus_options(record)
            and not PRICE_FIELDS.intersection(review))


def freeze_argument_review(review,record):
    """Explicitly review the original argument; never migrate a price assessment."""
    from research_history import question_digest
    if record['kind']!='original_question':raise ValueError('argument review requires an original question')
    if PRICE_FIELDS.intersection(review):raise ValueError('argument review cannot contain a price assessment')
    if review.get('question_digest')!=question_digest(record):raise ValueError('argument review original binding changed')
    validate_quote(review,record)
    scope=sorted(set(record['symbols']))
    focus=review.get('focused_symbol') or default_focus(record)
    if focus not in focus_options(record):raise ValueError('review needs an explicit related focused stock')
    if review.get('review_binding_version') and not argument_binding_matches(review,record):
        raise ValueError('argument review cannot rebind an existing assessment')
    for key,value in [('original_record_id',record['id']),('scope_symbols',scope),('assessment_basis',ARGUMENT_BASIS)]:
        if key in review and review[key]!=value:raise ValueError('argument review metadata conflicts with original')
    return {**review,'review_binding_version':ARGUMENT_VERSION,'assessment_basis':ARGUMENT_BASIS,
            'original_record_id':record['id'],'scope_symbols':scope,'focused_symbol':focus}


def validate_quote(review,record):
    clean=lambda text:re.sub(r'[\s*_>#`]','',text)
    quote=clean(review['then_quote'])
    if not quote or quote not in clean(' '.join(a['text'] for a in record['answers'])):
        raise ValueError('review quote is not in original answer')


def followthrough_claimed(review):
    return review.get('review_binding_version')==FOLLOWTHROUGH_VERSION or review.get('assessment_basis')==FOLLOWTHROUGH_BASIS


def followthrough_binding_matches(review,record):
    """A later study of an unanswered question must never become its old answer."""
    return (review.get('review_binding_version')==FOLLOWTHROUGH_VERSION
            and review.get('assessment_basis')==FOLLOWTHROUGH_BASIS
            and record['kind']=='original_question' and record.get('answers')==[]
            and review.get('then_quote')=='' and review.get('original_record_id')==record['id']
            and review.get('scope_symbols')==sorted(set(record['symbols']))
            and review.get('focused_symbol') in focus_options(record)
            and not PRICE_FIELDS.intersection(review))


def context_binding_matches(review,record):
    return followthrough_binding_matches(review,record) if followthrough_claimed(review) else argument_binding_matches(review,record)


def freeze_question_followthrough(review,record):
    from research_history import question_digest
    if (record['kind']!='original_question' or record.get('answers')!=[]
            or review.get('then_quote')!='' or PRICE_FIELDS.intersection(review)
            or review.get('question_digest')!=question_digest(record)):
        raise ValueError('question followthrough needs the exact unanswered original, no quote or trade assessment')
    focus=review.get('focused_symbol') or default_focus(record)
    fields={'review_binding_version':FOLLOWTHROUGH_VERSION,'assessment_basis':FOLLOWTHROUGH_BASIS,
            'original_record_id':record['id'],'scope_symbols':sorted(set(record['symbols'])),'focused_symbol':focus}
    if focus not in focus_options(record) or any(k in review and review[k]!=v for k,v in fields.items()):
        raise ValueError('question followthrough cannot relabel or rebind an existing review')
    return {**review,**fields}


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
    if argument_review_claimed(review) or followthrough_claimed(review):raise ValueError('context review needs its separate binding')
    validate_quote(review,record)
    scope=sorted(set(record['symbols']))
    focus=review.get('focused_symbol') or default_focus(record)
    if focus not in focus_options(record):raise ValueError('review needs an explicit related focused stock')
    through=through or paths['calendar'][-1]
    return {**review,'review_binding_version':VERSION,'price_through':through,'scope_symbols':scope,
            'focused_symbol':focus,'anchor_date':anchor,'price_window_digest':window_digest(paths,scope,anchor,through)}


def resolve_review(review,record,paths,question_digest,anchor):
    if not review:return {'review':None,'review_status':'not_reviewed'}
    if review.get('question_digest')!=question_digest:
        return {'review':None,'previous_review':review,'review_status':'original_changed'}
    if followthrough_claimed(review):
        if followthrough_binding_matches(review,record):return {'review':review,'review_status':'question_followthrough'}
        return {'review':None,'previous_review':review,'review_status':'review_basis_changed'}
    # A changed price must never conceal a fabricated quote in an unchanged answer.
    validate_quote(review,record)
    if argument_review_claimed(review):
        if argument_binding_matches(review,record):return {'review':review,'review_status':'argument_only'}
        return {'review':None,'previous_review':review,'review_status':'review_basis_changed'}
    if not review.get('review_binding_version'):
        matches=review.get('price_digest')==digest(paths)
    else:
        matches=False
        if (review['review_binding_version']==VERSION and review.get('scope_symbols')==sorted(set(record['symbols']))
                and review.get('anchor_date')==anchor and review.get('focused_symbol') in focus_options(record)):
            try:matches=review.get('price_window_digest')==window_digest(paths,review['scope_symbols'],anchor,review['price_through'])
            except (ValueError,KeyError,TypeError):pass
    if not matches:return {'review':None,'previous_review':review,'review_status':'price_changed'}
    status='new_observations' if review.get('price_through',paths['calendar'][-1])<paths['calendar'][-1] else 'current'
    return {'review':review,'review_status':status}
