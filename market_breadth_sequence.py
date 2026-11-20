"""An explicit, uncalibrated retrospective breadth condition; no strategy or probability fitting."""
from decimal import Decimal
from datetime import date
from market_calendar import sessions_2026

RULE = 'advancing_below_half_for_three_closes_first_hit_v1'

def analyze(history, index):
    if history.get('availability') != 'observed' or not history.get('complete_market_history'):
        raise ValueError('complete two-venue historical breadth required')
    points = history['points']
    expected = sessions_2026(date.fromisoformat(history['start']),date.fromisoformat(history['through']))
    if not points or [p['date'] for p in points] != expected:
        raise ValueError('breadth calendar has gaps or duplicates')
    calendar = index['calendar'];prices = index['indices']['000985.CSI']
    if [p['trade_date'] for p in prices] != calendar or len(set(calendar)) != len(calendar) or any(d not in calendar for d in expected):
        raise ValueError('verified benchmark dates required')
    if calendar != sessions_2026(date.fromisoformat(calendar[0]),date.fromisoformat(calendar[-1])):
        raise ValueError('benchmark calendar has gaps')
    bydate={p['trade_date']:Decimal(str(p['close'])) for p in prices}
    if any(not v.is_finite() or v<=0 for v in bydate.values()):raise ValueError('invalid benchmark close')
    days=[];signals=[];streak=0
    for p in points:
        a=p['all'];n=a['observed_trading_stocks'];up=a['advancing']
        if (type(n) is not int or n<=0 or any(type(a[k]) is not int or a[k]<0 for k in ('advancing','declining','flat','declining_5pct_or_more'))
            or a['declining_5pct_or_more']>a['declining'] or sum(a[k] for k in ('advancing','declining','flat'))!=n):
            raise ValueError('breadth denominator invalid')
        weak=up*2<n;streak=streak+1 if weak else 0
        row={'date':p['date'],'trading':n,'advancing':up,'declining':a['declining'],'flat':a['flat'],
             'advancing_pct':up/n*100,'declining_5pct_or_more':a['declining_5pct_or_more'],
             'streak':streak,'first_hit':streak==3}
        days.append(row)
        if streak==3:
            i=calendar.index(p['date']);end=calendar[i+5] if i+5<len(calendar) else None
            signals.append({'date':p['date'],'three_closes':[r['date'] for r in days[-3:]],
                            'advancing_pcts':[r['advancing_pct'] for r in days[-3:]],
                            'left_boundary_unknown':len(days)==3,
                            'after_five_on':end,'after_five_market_pct':float((bydate[end]/bydate[p['date']]-1)*100) if end else None})
    return {'rule':RULE,'start':history['start'],'through':history['through'],'observed_days':len(days),
            'weak_days':sum(r['advancing']*2<r['trading'] for r in days),'days':days,'signals':signals,
            'breadth_source_digest':history['content_digest'],'index_source_digest':index['content_digest'],
            'benchmark_through':index['through'],'historical_PIT':False,'method_promotions':0,
            'boundary':'上涨不足半数包含平盘，不能一概称多数下跌。连续计数只用已覆盖的当日及以前资料；仅在每段第三日记一次，后续弱日不重复计为案例。后5日是事后收盘对照，不假定提示日收盘成交，不是账户、策略收益或预警效果验证。'}
