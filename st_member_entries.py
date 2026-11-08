"""Primary-source entry causes and common-anchor descriptive observations."""
from canonical_json import digest
from st_member_transitions import membership_scope_digest
from math import prod


def entry_price_scope_digest(inputs):
    return digest({k:inputs[k] for k in ('members','calendar','through','fixed_prices','benchmarks','activities')})


def entry_observation(row, inputs, daily):
    calendar=inputs['calendar'];halt=row['suspend_on'];effective=row['effective_on']
    before=[d for d in calendar if d<halt];anchor=before[-1] if before else None
    following=[d for d in calendar if d>=effective];prices={(r['symbol'],r['trade_date']):r for r in inputs['fixed_prices']}
    first=prices.get((row['symbol'],anchor));windows={}
    for label,end in [('5',following[4] if len(following)>=5 else None),('20',following[19] if len(following)>=20 else None),('through',inputs['through'])]:
        last=prices.get((row['symbol'],end));obs=[r for r in daily if anchor and end and anchor<r['date']<=end]
        expected=[d for d in calendar if anchor and end and anchor<d<=end]
        complete=bool(end and obs and len(obs)==len(expected))
        traded=bool(first and last and first.get('has_trade') is True and last.get('has_trade') is True)
        windows[label]={'through':end,'market_days':len(obs) if complete else None,
                        'stock_pct':(last['close']/first['close']-1)*100 if complete and traded else None,
                        'market_pct':(prod(1+r['market_pct']/100 for r in obs)-1)*100 if complete else None,
                        'st_pct':(prod(1+r['return_pct']/100 for r in obs)-1)*100 if complete else None,
                        'gap':None if complete and traded else '窗口未满、端点缺价或不是实际交易收盘；未填零'}
    return {'anchor':anchor,'basis':'last_market_session_before_official_halt_to_effective_day_window',
            'not_earliest_reaction':True,'windows':windows}


def member_entry_view(inputs,daily):
    packet=inputs.get('member_entries')
    if packet is None:return None
    if packet['content_digest']!=digest({k:v for k,v in packet.items() if k!='content_digest'}):
        raise ValueError('member entry packet changed')
    if packet['through']!=inputs['through'] or packet['membership_scope_digest']!=membership_scope_digest(inputs) or packet['price_scope_digest']!=entry_price_scope_digest(inputs):
        raise ValueError('member entry scope binding changed')
    anchor=packet['anchor'];end=inputs['through'];prefixes=('000','001','002','003','600','601','603','605')
    initial={r['symbol'] for r in inputs['members'] if r['trade_date']==anchor and r['symbol'].startswith(prefixes)}
    endpoint={r['symbol'] for r in inputs['members'] if r['trade_date']==end and r['symbol'].startswith(prefixes)}
    rows=packet['rows']
    if len({r['symbol'] for r in rows})!=len(rows) or {r['symbol'] for r in rows}!=endpoint-initial:
        raise ValueError('member entry set changed')
    output=[]
    for row in rows:
        first=min(r['trade_date'] for r in inputs['members'] if r['symbol']==row['symbol'] and anchor<=r['trade_date']<=end)
        if row['first_provider_st']!=first or row['warning_type'] not in ('other','delisting') or not(row['announced_on']<=row['effective_on']<=end):
            raise ValueError('member entry stage/date changed')
        if row['cause_key'] not in ('reorganization_accepted','major_accounts_frozen','misstatement_notice','related_party_occupation'):
            raise ValueError('member entry cause classification unknown')
        if row['effective_on'] not in inputs['calendar'] or row['suspend_on'] not in inputs['calendar'] or row['suspend_on']>=row['effective_on']:
            raise ValueError('member entry halt/effective date invalid')
        for fact in row['facts']:
            if fact['published_on']>end or not all(fact['source'].get(k) for k in ('sha256','url','page','title')):
                raise ValueError('member entry lacks timely source')
        output.append({**row,'effective_matches_membership':first==row['effective_on'],'observation':entry_observation(row,inputs,daily)})
    return {'anchor':anchor,'through':end,'rows':output,'total':len(output),'matching_boundaries':sum(r['effective_matches_membership'] for r in output),
            'composition':{'initial':len(initial),'entered':len(endpoint-initial),'left':len(initial-endpoint),'endpoint':len(endpoint)},
            'boundary':'本轮只核6个新增边界和既有14个移出边界；不是全部日历成员、价格或公司正文的穷尽认证。价格对照按共同日期描述，不分摊公告、ST标签或大盘的因果贡献。'}
