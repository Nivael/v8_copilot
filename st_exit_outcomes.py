"""Provider-list disappearance, formal removal and delisting have different meanings."""
from copy import deepcopy
from decimal import Decimal as D
from statistics import median
from canonical_json import digest

def exit_outcomes(inputs, priors):
    packet=inputs.get('exit_outcomes')
    if packet is None:return None
    if packet.get('version')!=1 or packet.get('content_digest')!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('exit outcomes packet changed')
    if digest(priors)!=PRIOR_DIGEST:raise ValueError('exit outcomes prior changed')
    market=inputs['current_extension']['market_inputs']
    if digest({'members':market['members'],'calendar':market['calendar']})!=MEMBERSHIP_DIGEST:raise ValueError('exit outcomes membership changed')
    audit=priors['endpoint_selection_audit'];cohort=priors['removal_cohort'];reasons=priors['endpoint_reasons']
    dates=[d for d in market['calendar']if d>='2026-07-03'];members={d:set()for d in dates}
    for row in market['members']:
        if row['trade_date']in members:members[row['trade_date']].add(row['symbol'])
    outside=[r for r in audit['windows'][0]['rows']if not r['provider_st_at_end']]
    if len(outside)!=14:raise ValueError('exit outcomes original population changed')
    rows=[]
    for row in outside:
        code=row['symbol'];c=next((r for r in cohort['rows']if r['symbol']==code),None);first=next(d for d in dates if code not in members[d])
        if code not in members[dates[0]]:raise ValueError('exit outcomes initial member missing')
        if c:
            if first!=c['effective_on']:raise ValueError('exit outcomes removal date mismatch')
            kind='warning_removed';effective=c['effective_on'];facts=c['facts'];name=c['name'];warning=c['warning_removed']
        else:
            c=next(r for r in cohort['excluded']if r['symbol']==code)
            if first!=c['provider_first_absent']:raise ValueError('exit outcomes stage date mismatch')
            kind='voluntary_delisting'if code=='000016'else'delisting_period_then_delisted';effective='2026-10-23';facts=c['facts'];name='康佳A'if code=='000016'else'萃华';warning=None
        if not all(code not in members[d]for d in dates if d>=first):raise ValueError('exit outcomes provider reentry')
        latest=next((r for r in reasons['cases']if r['symbol']==code),None);returns=[]
        for window in audit['windows']:
            a=next(r for r in window['rows']if r['symbol']==code);returns.append({'window':window['key'],'anchor':window['anchor'],'through':window['through'],'status':a['status'],'certified_return_pct':a['certified_return_pct'],'primary_return_pct':a['primary_return_pct']})
        rows.append({'symbol':code,'name':name,'classification':kind,'warning_removed':warning,'provider_first_absent':first,'official_effective_or_stage_date':effective,'provider_no_reentry_through':'2026-11-19','facts':facts,'later_reading':latest['reading']if latest else None,'later_sources':latest['sources']if latest else [],'returns':returns})
    removed=[r for r in rows if r['classification']=='warning_removed'];summary=[]
    if len(removed)!=12:raise ValueError('exit outcomes removal population changed')
    for n in range(2):
        values=[D(r['returns'][n]['certified_return_pct'])for r in removed if r['returns'][n]['certified_return_pct']is not None]
        summary.append({'window':removed[0]['returns'][n]['window'],'members':12,'verified_paired':len(values),'positive':sum(x>0 for x in values),'median_pct':str(median(values))})
    expected=packet['result']
    if digest(expected)!=VIEW_DIGEST or expected['rows']!=rows or expected['removed_return_summary']!=summary:raise ValueError('exit outcomes result changed')
    return deepcopy(expected)

PRIOR_DIGEST='f5b5c97d08930e89ed99b879e9fe073fc21460646378ed979518753d258fd69a'
MEMBERSHIP_DIGEST='990b0b5c6da176fef9c62b37b45ede3a29b5f968f1c1b18970624e5ce87c47cf'
VIEW_DIGEST='9ad8cb619c334bcd5b6c26278a1d57aff087856d7d33a88922cc58e8194fdec0'
