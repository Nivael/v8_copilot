import pytest
from st_period_event_windows import event_windows

def data():
    days=['2026-07-03','2026-07-06','2026-07-07']
    market={'fixed_prices':[dict(symbol='002431',trade_date=d,close=v,has_trade=True)for d,v in zip(days,[10,11,12])], 'benchmarks':[dict(benchmark_id='csi_all_share',trade_date=d,close=v)for d,v in zip(days,[100,101,102])]}
    daily=[dict(date='2026-05-07',return_pct=99),dict(date='2026-07-07',return_pct=2),dict(date='2026-07-06',return_pct=1)]
    return market,daily,[dict(announcement_id='one',symbol='002431',published_on='2026-07-04')]

def test_weekend_disclosure_ignores_earlier_history_and_sorts_trading_days():
    m,d,s=data();result=event_windows(m,d,s,through='2026-07-07')[0]['windows']
    assert result[0]['anchor']=='2026-07-03' and result[0]['through']=='2026-07-06'
    assert result[0]['stock_pct']=='10.0' and result[0]['st_pct']=='1.00'
    assert result[1]['observed_days']==2 and result[1]['status']=='unfinished'
    assert result[1]['st_pct']=='3.0200'

def test_pre_anchor_source_is_not_a_new_catalyst():
    m,d,s=data();s[0]['published_on']='2026-07-03';assert event_windows(m,d,s,through='2026-07-07')==[]

@pytest.mark.parametrize('kind',['duplicate_day','duplicate_source','future','nontraded','missing_final','zero_price'])
def test_rejects_invalid_scope_and_endpoints(kind):
    m,d,s=data()
    if kind=='duplicate_day':d.append(d[-1])
    elif kind=='duplicate_source':s.append(s[0])
    elif kind=='future':s[0]['published_on']='2026-07-08'
    elif kind=='nontraded':m['fixed_prices'][1]['has_trade']=False
    elif kind=='missing_final':d=[r for r in d if r['date']!='2026-07-07']
    elif kind=='zero_price':m['fixed_prices'][0]['close']=0
    with pytest.raises(ValueError):event_windows(m,d,s,through='2026-07-07')
