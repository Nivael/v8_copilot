"""Explain fixed-sample gaps without turning suspensions or exits into returns."""
from canonical_json import digest


def price_scope_digest(inputs):
    return digest({key:inputs[key] for key in ('calendar','fixed_prices','through')})


def load_integrity(inputs):
    packet=inputs.get('sample_integrity')
    if packet is None:
        return None
    if packet.get('content_digest') != digest({k:v for k,v in packet.items() if k!='content_digest'}):
        raise ValueError('sample integrity packet changed')
    if packet.get('through') != inputs['through'] or packet.get('price_scope_digest') != price_scope_digest(inputs):
        raise ValueError('sample integrity price/window binding changed')
    cases=packet['cases']
    if len({c['symbol'] for c in cases}) != len(cases):
        raise ValueError('duplicate sample integrity case')
    prices={(r['symbol'],r['trade_date']):r['close'] for r in inputs['fixed_prices']}
    for case in cases:
        if case['as_of']!=inputs['through'] or case['classification'] not in ('anchor_suspended','endpoint_delisted'):
            raise ValueError('sample integrity scope/classification changed')
        symbol=case['symbol']
        for field in ('anchor','endpoint'):
            point=case[field]
            if prices.get((symbol,point['date'])) != point['close']:
                raise ValueError('sample integrity endpoint changed')
        if case['classification']=='anchor_suspended' and case['anchor']['close'] is not None:
            raise ValueError('suspended missing anchor unexpectedly filled')
        if case['classification']=='endpoint_delisted' and case['endpoint']['close'] is not None:
            raise ValueError('delisted endpoint unexpectedly filled')
        for fact in case['facts']:
            source=fact['source']
            if fact['published_on']>case['as_of'] or not all(source.get(k) for k in ('url','sha256','page','title')):
                raise ValueError('sample integrity fact lacks timely source')
    return packet


def fixed_gap_note(packet,symbol,anchor,through):
    if packet:
        for case in packet['cases']:
            if case['symbol']==symbol and case['anchor']['date']==anchor and case['endpoint']['date']==through:
                return {'classification':case['classification'],'title':case['title'],'explanation':case['explanation'],
                        'as_of':case['as_of'],'boundary':case['boundary'],'facts':case['facts']}
    return None
