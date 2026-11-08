"""Question-oriented, descriptive views of the frozen ST comparison input."""
from collections import Counter
from math import prod
from statistics import mean
from canonical_json import digest


def compound(rows, field):
    return (prod(1 + r[field] / 100 for r in rows) - 1) * 100 if rows else None


def event_context(event, symbol, inputs, daily):
    calendar = inputs['calendar']
    day = event['published_on']
    eligible = [d for d in calendar if d <= day]
    anchor = eligible[-1] if eligible else None
    prices = {(r['symbol'],r['trade_date']):r['close'] for r in inputs['fixed_prices']}
    start = prices.get((symbol, anchor))
    windows = {}
    for n in (1,5,20):
        remaining = [d for d in calendar if anchor and d > anchor]
        end = remaining[n-1] if len(remaining) >= n else None
        close = prices.get((symbol,end))
        rows = [r for r in daily if anchor and end and anchor < r['date'] <= end]
        valid = bool(end and len(rows) == n)
        windows[str(n)] = {'through':end,'stock_pct':(close/start-1)*100 if start and close and valid else None,
                          'market_pct':compound(rows,'market_pct') if valid else None,
                          'st_pct':compound(rows,'return_pct') if valid else None,
                          'gap':None if start and close and valid else '起止缺价或后续交易日不足，未填零'}
    return {'anchor':anchor,'date_precision':'day','not_earliest_reaction':True,'windows':windows}


def build_themes(inputs, daily):
    after = [r for r in daily if r['date'] >= '2026-07-06']
    months = []
    for month in sorted({r['date'][:7] for r in after}):
        rows = [r for r in after if r['date'].startswith(month)]
        months.append({'month':month,'start':rows[0]['date'],'through':rows[-1]['date'],'days':len(rows),
                       'st_pct':compound(rows,'return_pct'),'market_pct':compound(rows,'market_pct'),
                       'small_pct':compound(rows,'small_cap_pct'),
                       'positive_breadth_pct':mean(r['positive_pct'] for r in rows)})
    extreme = sorted(sorted(after,key=lambda r:abs(r['market_pct']),reverse=True)[:8],key=lambda r:r['date'])
    result = {'months':months,'market_days':[{k:r[k] for k in ('date','market_pct','return_pct','positive_pct')} for r in extreme]}
    packet = inputs.get('announcement_study')
    if not packet:
        return result
    if packet['content_digest'] != digest({k:v for k,v in packet.items() if k!='content_digest'}):
        raise ValueError('announcement source packet changed')
    catalogs = packet['catalogs']
    events = []
    names = {s:c['name'] for s,c in catalogs.items()}
    for event in packet['verified_events']:
        symbol = event['symbol']
        context=event_context(event,symbol,inputs,daily)
        alternative=event_context({**event,'published_on':event['alternate_published_on']},symbol,inputs,daily) if event.get('alternate_published_on') else None
        events.append({**event,'name':names[symbol],'observation':context,'alternate_observation':alternative})
    result['announcements'] = {'from':packet['start'],'through':packet['through'],
        'companies':len(catalogs),'catalog_rows':sum(len(c['rows']) for c in catalogs.values()),
        'catalog_pages':sum(len(c['source_refs']) for c in catalogs.values()),
        'verified_events':events,'verified_companies':len({e['symbol'] for e in events}),
        'verified_documents':len({(e['symbol'],e['source']['sha256']) for e in events}),
        'catalog_by_month':dict(sorted(Counter(r['announcement_date'][:7] for c in catalogs.values() for r in c['rows']).items())),
        'history_digest':packet['history_digest'],'source_packet_digest':packet['content_digest'],
        'body_reads_this_refresh':0,
        'boundary':'目录覆盖156家指定公司与7月1日至11月6日窗口；正文事实来自已核历史资料的选样，不能代表全体公告。日期仅精确到日，行情从披露日或之前最近收盘后起算，不认证最早反应或公告因果。'}
    changes = inputs.get('refresh_provenance',{}).get('prior_activity_differences',[])
    result['refresh'] = {'through':inputs['through'],'prior_input_digest':inputs.get('refresh_provenance',{}).get('prior_input_digest'),
                          'activity_differences':len(changes)}
    return result
