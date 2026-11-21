"""Observed consecutive limit states; never bridge missing or nonmember days."""
from datetime import date
from market_calendar import sessions_2026

METRICS=('close_at_down','one_price_down')


def analyze(reading):
    days=sessions_2026(date.fromisoformat(reading['start']),date.fromisoformat(reading['through']))
    groups=[]
    for group in reading['groups']:
        if [r['date']for r in group['days']]!=days:raise ValueError('cohort calendar changed')
        rows={}
        for row in group['rows']:
            key=(row['symbol'],row['date'])
            if key in rows or row['date']not in days:raise ValueError('duplicate or out-of-window observation')
            if row['status']=='paired':
                if any(type(row[k])is not bool for k in METRICS):raise ValueError('explicit paired states required')
                if row['one_price_down']and not row['close_at_down']:raise ValueError('inconsistent limit state')
            rows[key]=row
        for day in group['days']:
            if sum(d==day['date']for _,d in rows)!=day['members']:raise ValueError('member observation count changed')
        symbols=sorted({s for s,_ in rows});runs=[]
        def state(symbol,day,metric):
            row=rows.get((symbol,day))
            if row is None:return 'not_member'
            if row['status']!='paired':return row['status']
            return 'hit'if row[metric]else'observed_nonhit'
        for symbol in symbols:
            for metric in METRICS:
                n=0
                while n<len(days):
                    if state(symbol,days[n],metric)!='hit':n+=1;continue
                    first=n
                    while n<len(days)and state(symbol,days[n],metric)=='hit':n+=1
                    left='window_edge'if first==0 else state(symbol,days[first-1],metric)
                    right='window_edge'if n==len(days)else state(symbol,days[n],metric)
                    names=[rows[symbol,d]['name']for d in days[first:n]if rows[symbol,d].get('name')]
                    runs.append({'symbol':symbol,'name':names[0]if names else symbol,'metric':metric,
                                 'dates':days[first:n],'observed_sessions':n-first,
                                 'left_reason':left,'right_reason':right,
                                 'left_boundary_unknown':left!='observed_nonhit',
                                 'right_boundary_unknown':right!='observed_nonhit',
                                 'ongoing_at_cutoff':n==len(days)})
        metrics=[]
        for metric in METRICS:
            blocks=[r for r in runs if r['metric']==metric];continuous=[r for r in blocks if r['observed_sessions']>=2]
            metrics.append({'metric':metric,'observed_hit_sessions':sum(len(r['dates'])for r in blocks),
                            'blocks_including_singletons':len(blocks),'continuous_blocks':len(continuous),
                            'continuous_companies':len({r['symbol']for r in continuous}),
                            'longest_observed_sessions':max((len(r['dates'])for r in blocks),default=0)})
        groups.append({'key':group['key'],'metrics':metrics,'runs':runs,
                       'unpaired_observations':sum(r['status']!='paired'for r in rows.values())})
    return {'version':'st_limit_streaks_v1','start':days[0],'through':days[-1],'groups':groups,
            'boundary':'连续按交易日历计数，不跨缺日线、未核配限价或不在当日组的日期连段。窗口边界或缺失相邻日的真实起止未知，长度只是可观察连续日数；两组重叠股票和两种状态不增加独立案例。收盘达到下限不等于全天同价，全天同价不直接证明某笔委托无法成交。',
            'independent_validations_added':0}
