"""Audit the chronology and scope of a retrospective, not its investment merit.

Passing these checks makes an event/price comparison reviewable. It never proves
that an event caused a return or that a lesson generalizes to another company.
"""
from datetime import date
from decimal import Decimal


def _day(value):
    return date.fromisoformat(value).isoformat()


def audit_events(events):
    """Reject look-ahead, reaction-as-cause and silent changes of entity/stage."""
    seen={};previous=''
    for event in events:
        key=event['id'];published=_day(event['published_on'])
        if not key or key in seen or published<previous:raise ValueError('event identities or publication order changed')
        previous=published
        if event['publication_precision']!='day':raise ValueError('this profile cannot certify a first-public minute')
        if event['entity_scope'] not in {'issuer','subsidiary','shareholder'}:raise ValueError('event entity is unresolved')
        if not event.get('source_id') or not event.get('fact') or not event.get('state_before') or not event.get('state_after'):
            raise ValueError('event needs its source and before/after fact states')
        if event['change_kind'] not in {'new_fact','progress','reaffirmation','outcome_report'}:raise ValueError('event change kind is unresolved')
        occurred=event.get('occurred_on')
        if occurred and _day(occurred)>published and event['state_after']!='scheduled':raise ValueError('future event cannot be recorded as completed')
        if event['change_kind']=='reaffirmation':
            earlier=seen.get(event.get('reaffirms'))
            if not earlier or event['state_before']!=event['state_after'] or earlier['state_after']!=event['state_after'] or earlier['entity_scope']!=event['entity_scope']:
                raise ValueError('reaffirmation needs its unchanged earlier state')
        if event.get('inferred_transition') and event['inferred_transition']!=event['state_after']:
            raise ValueError('a related entity or a later process stage cannot be silently substituted')
        claim=event.get('price_cause_claim')
        if claim:
            if event['change_kind']=='outcome_report':raise ValueError('a reaction report cannot be used as the cause of that reaction')
            if _day(claim['move_started_on'])<=published:raise ValueError('day-only disclosure cannot establish an earlier or same-day cause')
            if claim.get('identified') is not False:raise ValueError('this chronology profile does not identify causal effects')
        seen[key]=event
    return {'events':len(events),'chronology_checked':True,'causal_effect_identified':False,'cross_case_generalization_tested':False}


def following_windows(points,market,st,calendar,published_on,*,counts=(1,5)):
    """Next complete sessions after the disclosure day; never earliest reaction.

    Trading-day releases use that day's close as reference. Weekend releases use
    the preceding market close. A missing stock quote leaves the result missing;
    it must not move the anchor or turn the gap into a zero return.
    """
    day=_day(published_on)
    if calendar!=sorted(set(calendar)):raise ValueError('calendar must be unique and ordered')
    prior=[d for d in calendar if d<=day];following=[d for d in calendar if d>day]
    anchor=prior[-1] if prior else None
    indexed=[]
    for series in [points,market,st]:
        dates=[p['date'] for p in series]
        if len(dates)!=len(set(dates)) or any(d not in calendar for d in dates):raise ValueError('series dates differ from the comparison calendar')
        indexed.append({p['date']:p['level'] for p in series})
    result={'published_on':day,'reference_close':anchor,'window_basis':'complete_sessions_after_disclosure_day','not_earliest_reaction':True,'windows':{}}
    for count in counts:
        if type(count) is not int or count<=0:raise ValueError('positive whole-session window required')
        end=following[count-1] if count<=len(following) else None;values={}
        for label,series in zip(['stock','market','st'],indexed):
            start=series.get(anchor);last=series.get(end)
            if start is None or last is None:values[label]=None
            else:
                a,b=Decimal(str(start)),Decimal(str(last))
                if not a.is_finite() or not b.is_finite() or min(a,b)<=0:raise ValueError('invalid comparison level')
                values[label]=str((b/a-1)*100)
        result['windows'][str(count)]={'through':end,'change_pct':values}
    return result


def reconcile_holdings(before,after,transferred):
    """A disclosed arithmetic conflict is a data debt, not an invented correction."""
    values=[Decimal(str(v)) for v in [before,after,transferred]]
    if any(not x.is_finite() or x<0 or x!=x.to_integral_value() for x in values):raise ValueError('share counts must be nonnegative integers')
    stated_reduction=values[0]-values[1]
    return {'consistent':stated_reduction==values[2],'stated_reduction':int(stated_reduction),'listed_transfer':int(values[2]),'unreconciled_difference':int(stated_reduction-values[2]),'silently_corrected':False}
