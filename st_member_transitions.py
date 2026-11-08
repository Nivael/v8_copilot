"""Validate sourced fixed-cohort exit stages against point-in-time membership."""
from collections import Counter
from canonical_json import digest


def membership_scope_digest(inputs):
    return digest({k:inputs[k] for k in ('members','calendar','through')})


def member_transition_view(inputs):
    packet=inputs.get('member_transitions')
    if packet is None:return None
    if packet['content_digest']!=digest({k:v for k,v in packet.items() if k!='content_digest'}):
        raise ValueError('member transition packet changed')
    if packet['through']!=inputs['through'] or packet['membership_scope_digest']!=membership_scope_digest(inputs):
        raise ValueError('member transition membership binding changed')
    anchor=packet['anchor'];end=inputs['through'];calendar=inputs['calendar']
    baseline={r['symbol'] for r in inputs['members'] if r['trade_date']==anchor and r['symbol'].startswith(('000','001','002','003','600','601','603','605'))}
    endpoint={r['symbol'] for r in inputs['members'] if r['trade_date']==end}
    rows=packet['rows']
    if len({r['symbol'] for r in rows})!=len(rows) or {r['symbol'] for r in rows}!=baseline-endpoint:
        raise ValueError('member transition exit set changed')
    output=[]
    for row in rows:
        if row['status'] not in ('warning_removed','voluntary_delisted','delisting_period'):
            raise ValueError('unknown member transition status')
        dates=[r['trade_date'] for r in inputs['members'] if r['symbol']==row['symbol'] and anchor<=r['trade_date']<=end]
        last=max(dates);absent=next((d for d in calendar if d>last),None)
        if last!=row['provider_last_st'] or absent!=row['provider_first_absent']:
            raise ValueError('member transition dates changed')
        if not (row['announced_on']<=row['effective_on']<=end and row['effective_on'] in calendar):
            raise ValueError('member transition effective date outside scope')
        if row.get('approval_on') and row['approval_on']>row['announced_on']:
            raise ValueError('member transition approval date follows announcement')
        for fact in row['facts']:
            source=fact['source']
            if fact['published_on']>end or not all(source.get(k) for k in ('sha256','title','url','page')):
                raise ValueError('member transition fact lacks timely source')
        output.append({**row,'effective_matches_membership':row['effective_on']==absent})
    counts=Counter(r['status'] for r in output)
    return {'anchor':anchor,'through':end,'rows':output,'counts':dict(counts),'total':len(output),
            'matching_boundaries':sum(r['effective_matches_membership'] for r in output),
            'boundary':'只核固定7月3日名单至期末的14个移出边界。撤销风险警示不等于全部经营、诉讼或监管风险消失；全部逐日成员仍需扩大独立核对。'+('新增边界另见新增公司明细。' if inputs.get('member_entries') else '新增公司的原因尚未在本表认证。')}
