"""Same-close retrospective comparison; no executable signal or probability claim."""
from decimal import Decimal as D
from datetime import date
from market_calendar import sessions_2026

def analyze(st, breadth):
    extension=st['themes']['current_extension']
    daily=st['daily']+extension['days']
    dates=[r['date'] for r in daily]
    if len(set(dates))!=len(dates):raise ValueError('duplicate ST day')
    if dates!=sessions_2026(date.fromisoformat(dates[0]),date.fromisoformat(dates[-1])):raise ValueError('ST calendar gap')
    rows=breadth['sequence']['days']
    bd=[r['date'] for r in rows]
    if bd!=sessions_2026(date.fromisoformat(bd[0]),date.fromisoformat(bd[-1])):raise ValueError('breadth calendar gap')
    bydate={r['date']:r for r in daily}
    common=[d for d in bd if d in bydate]
    if common!=[d for d in bd if d<=dates[-1]]:raise ValueError('missing common date')
    def number(v):
        n=D(str(v))
        if not n.is_finite():raise ValueError('nonfinite return')
        return n
    for r in daily:
        if r['missing'] or r['observed_count']<=0:raise ValueError('unresolved ST coverage')
        for k in ('return_pct','market_pct'): 
            if number(r[k])<=-100:raise ValueError('invalid return')
    signals=[];streak=0
    for i,r in enumerate(rows):
        n=r['trading'];up=r['advancing']
        if type(n)is not int or n<=0 or not 0<=up<=n:raise ValueError('bad denominator')
        streak=streak+1 if up*2<n else 0
        if streak!=3 or r['date'] not in common:continue
        start=common.index(r['date']);after=common[start+1:start+6]
        def compound(key):
            value=D(1)
            for d in after:value*=1+number(bydate[d][key])/100
            return float((value-1)*100) if after else None
        sr,mr=compound('return_pct'),compound('market_pct')
        signals.append({'date':r['date'],'three_closes':bd[i-2:i+1],'observed_following_sessions':len(after),'through':after[-1] if after else r['date'],'complete_five':len(after)==5,'st_pct':sr,'market_pct':mr,'st_minus_market_pp':sr-mr if sr is not None else None,'five_st_pct':sr if len(after)==5 else None,'five_market_pct':mr if len(after)==5 else None})
    return {'version':'st_breadth_alignment_v1','common_start':common[0],'common_through':common[-1],'common_days':len(common),'breadth_through':bd[-1],'st_through':dates[-1],'signals':signals,'method_promotions':0}
