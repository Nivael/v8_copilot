"""Observed first-three-close moves, kept separate from later returns."""
from decimal import Decimal as D
from st_breadth_alignment import analyze

def analyze_timing(e):
    i=e['inputs'];st={'daily':i['daily'],'themes':{'current_extension':{'days':i['extension_days']}}};b={'sequence':{'days':i['breadth_days']}}
    result=analyze(st,b)
    if result!=e['reading']:raise ValueError('frozen alignment failed replay')
    daily=i['daily']+i['extension_days'];bydate={r['date']:r for r in daily};dates=[r['date'] for r in daily]
    def change(ds,key):
        value=D(1)
        for d in ds:value*=1+D(str(bydate[d][key]))/100
        return float((value-1)*100)
    rows=[]
    for signal in result['signals']:
        three=signal['three_closes'];j=dates.index(three[0]);anchor=dates[j-1] if j else None
        # The preceding close is essential; do not turn a first close into its own anchor.
        if anchor is None:raise ValueError('preceding anchor missing')
        rows.append({'first_weak_day':three[0],'anchor':anchor,'signal_date':signal['date'],'observed_closes':3,'already_st_pct':change(three,'return_pct'),'already_market_pct':change(three,'market_pct'),'following':signal})
    return {'version':'st_breadth_timing_v1','rows':rows,'boundary':'前三日变动在提示收盘已发生，不是提示后的损失；前后复合，不能直接相加，也不推定提示前持仓或提前可卖出。'}
