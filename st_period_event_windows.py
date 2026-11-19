"""Descriptive post-disclosure windows with an explicit ordered trading calendar."""
from decimal import Decimal as D

def event_windows(market, daily, sources, anchor='2026-07-03', through='2026-11-19'):
    dates=[r['date'] for r in daily if anchor < r['date'] <= through]
    if len(dates)!=len(set(dates)):
        raise ValueError('duplicate daily reference date')
    calendar=sorted({anchor,*dates})
    if not dates or calendar[-1]!=through:
        raise ValueError('missing final market date')
    reference={r['date']:r for r in daily}
    prices={(r['symbol'],r['trade_date']):r for r in market['fixed_prices']}
    benchmarks={(r['benchmark_id'],r['trade_date']):D(str(r['close'])) for r in market['benchmarks']}
    result=[]
    seen=set()
    for source in sources:
        aid=source['announcement_id'];published=source['published_on'];symbol=source['symbol']
        if aid in seen:raise ValueError('duplicate announcement window')
        seen.add(aid)
        if published<=anchor:continue
        if published>through:raise ValueError('future disclosure')
        baseline=max(day for day in calendar if day<published)
        after=[day for day in calendar if day>baseline]
        windows=[]
        for requested in (1,5,20):
            observed=after[:requested];end=observed[-1]
            start_price,end_price=(prices[(symbol,d)] for d in (baseline,end))
            if not start_price['has_trade'] or not end_price['has_trade']:
                raise ValueError('nontraded event endpoint')
            if D(str(start_price['close']))<=0 or D(str(end_price['close']))<=0:
                raise ValueError('nonpositive event price')
            stock=(D(str(end_price['close']))/D(str(start_price['close']))-1)*100
            broad=(benchmarks[('csi_all_share',end)]/benchmarks[('csi_all_share',baseline)]-1)*100
            compound=D(1)
            for day in observed:compound*=1+D(str(reference[day]['return_pct']))/100
            windows.append(dict(requested_days=requested,observed_days=len(observed),anchor=baseline,through=end,status='complete' if len(observed)==requested else 'unfinished',stock_pct=str(stock),market_pct=str(broad),st_pct=str((compound-1)*100)))
        result.append(dict(aid=aid,symbol=symbol,published_on=published,windows=windows))
    return result
