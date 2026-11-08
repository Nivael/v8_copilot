from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from st_regime_comparison import (
    VERSION, daily_observation, compounded, quantile, relation, period_metrics,
    main_board, load, publish, extract_inputs, build,
)


def fact(symbol='600001', **changes):
    return dict(symbol=symbol, pct_chg=1., pre_close=2.91, close=2.94, volume=100.,
                turnover_rate_f=5., suspension_status='trading', terminal_phase_status='not_terminal', **changes)


def test_rounding_old_limit_is_price_bound_not_approximate_percentage():
    row=fact(); row.update(close=2.76,pct_chg=-5.1546)
    result=daily_observation({'600001':{}},{'600001':row})
    assert result['beyond_old_down_pct']==0
    row.update(close=2.75,pct_chg=-5.4983)
    assert daily_observation({'600001':{}},{'600001':row})['beyond_old_down_pct']==100
    row.update(pre_close=2.13,close=2.24,pct_chg=5.1643)
    assert daily_observation({'600001':{}},{'600001':row})['beyond_old_up_pct']==0


def test_one_tick_minimum_at_very_low_prices():
    row=fact();row.update(pre_close=.08,close=.09,pct_chg=12.5)
    assert daily_observation({'600001':{}},{'600001':row})['beyond_old_up_pct']==0


def test_suspensions_unknown_and_terminal_are_not_flat_or_successful():
    valid=fact(); suspended=fact('600002');suspended['suspension_status']='suspended'
    unknown=fact('600003');unknown['suspension_status']='unknown'
    terminal=fact('600004');terminal['terminal_phase_status']='terminal'
    rows={r['symbol']:r for r in [valid,suspended,unknown,terminal]}
    result=daily_observation(dict.fromkeys([*rows,'600005'],{}),rows)
    assert result['member_count']==5 and result['observed_count']==1
    assert result['return_pct']==1 and result['positive_pct']==100 and result['coverage_pct']==20
    assert result['suspended']==['600002']
    assert result['missing']==['600003','600005']
    assert result['terminal_excluded']==['600004']


def test_missing_returns_never_compound_as_zero():
    assert compounded([10,-10])==pytest.approx(-1)
    assert compounded([None,10]) is None
    assert compounded([]) is None


def test_quantile_linear_interpolation():
    assert quantile([0,10,20,30],.1)==pytest.approx(3)
    assert quantile([], .9) is None


@pytest.mark.parametrize('symbol,expected',[('600001',True),('002001',True),('000001',True),('300001',False),('688001',False),('830001',False),('900001',False),('200001',False),('600001.SH',False)])
def test_rule_applies_only_to_main_board_a_shares(symbol,expected):
    assert main_board(symbol)==expected


def test_relation_is_sample_covariance_not_causal_attribution():
    result=relation([{'market_pct':x,'return_pct':2*x+1} for x in [-1,0,1]])
    assert result['correlation']==pytest.approx(1)
    assert result['beta']==pytest.approx(2)
    assert relation([{'market_pct':1,'return_pct':2}]*4)['correlation'] is None


@pytest.fixture(scope='module')
def frozen():
    # Integration runs use a small scoped input, without mutating any source DB.
    from settings import BASE_DB, MARKET_CONTEXT_DB, MARKET_ACTIVITY_DB
    if not all(path.is_file() for path in (BASE_DB,MARKET_CONTEXT_DB,MARKET_ACTIVITY_DB)):
        pytest.skip('optional local historical input databases are not installed')
    return extract_inputs()


def test_real_windows_are_symmetric_and_include_first_effective_day(frozen):
    data=build(frozen)
    c=next(c for c in data['comparisons'] if c['key']=='40')
    assert c['before']['days']==c['after']['days']==40
    assert c['before']['through']=='2026-07-03'
    assert c['after']['start']=='2026-07-06'
    assert c['after']['through']=='2026-08-28'
    assert c['fixed_after']['total']==150
    assert len(c['fixed_after']['rows'])==150
    assert c['fixed_after']['covered']+c['fixed_after']['missing']==150
    assert c['before']['beyond_old_down_pct']==c['before']['beyond_old_up_pct']==0
    assert c['after']['missing_observations']==0
    assert c['after']['trading_observations']+c['after']['suspended_observations']==c['after']['member_observations']
    assert c['before']['reference_change_pct']==pytest.approx(-10.537528237473948)
    assert c['after']['reference_change_pct']==pytest.approx(.538884128723871)
    assert c['after']['mean_dispersion_pp']<c['before']['mean_dispersion_pp']
    assert c['after']['daily_volatility_pct']>c['before']['daily_volatility_pct']


@pytest.mark.parametrize('change',['membership','calendar','duplicate','quote','terminal'])
def test_real_publication_fails_closed_on_gaps(frozen,change):
    bad=deepcopy(frozen)
    if change=='membership':
        bad['members']=[r for r in bad['members'] if r['trade_date']!='2026-07-06']
    elif change=='calendar':
        bad['calendar'].remove('2026-07-06')
    elif change=='duplicate':
        bad['activities'].append(bad['activities'][0])
    elif change=='quote':
        row=next(r for r in bad['activities'] if r['trade_date']=='2026-07-06')
        row['suspension_status']='unknown'
    else:
        row=next(r for r in bad['activities'] if r['trade_date']=='2026-07-06')
        row['terminal_phase_status']='unknown'
    with pytest.raises(ValueError):build(bad)


def test_all_period_is_not_disguised_as_equal_windows(frozen):
    all_window=build(frozen)['comparisons'][-1]
    assert all_window['before']['days']==40 and all_window['after']['days']==44
    assert all_window['key']=='all'


def test_snapshot_hash_binds_original_inputs_and_code(frozen,tmp_path):
    value=publish(frozen,root=tmp_path)
    assert load(tmp_path)['content_digest']==value['content_digest']
    source=tmp_path/value['source_asset']
    raw=json.loads(gzip.decompress(source.read_bytes()))
    raw['through']='2026-09-04'
    source.write_bytes(gzip.compress(json.dumps(raw).encode()))
    assert load(tmp_path)['availability']=='unavailable'


def test_publication_retains_missing_fixed_members(frozen):
    data=build(frozen);c=data['comparisons'][0]
    missing=[r for r in c['fixed_after']['rows'] if r['return_pct'] is None]
    assert missing and all(r['gap'] for r in missing)
    matched=set(c['paired']['symbols'])
    pre={r['symbol'] for r in c['fixed_before']['rows'] if r['return_pct'] is not None}
    post={r['symbol'] for r in c['fixed_after']['rows'] if r['return_pct'] is not None}
    assert matched==pre&post


def synthetic_inputs():
    from datetime import date
    from market_calendar import sessions_2026
    days=sessions_2026(date(2026,5,6),date(2026,9,3))
    inputs={'version':VERSION,'calendar':days,'through':days[-1],'members':[],'activities':[],'benchmarks':[],'fixed_prices':[],'source_tables':[]}
    price=10.
    for index,day in enumerate(days):
        prior=price;price=round(price*(1.01 if day<'2026-07-06' else .99),2)
        rate=(price/prior-1)*100
        inputs['members'].extend([{'trade_date':day,'symbol':'600001','name':'ST测试'},{'trade_date':day,'symbol':'300001','name':'ST不受本次变更影响'}])
        inputs['activities'].append({**fact(), 'trade_date':day,'close':price,'pre_close':prior,'pct_chg':rate})
        inputs['fixed_prices'].append({'trade_date':day,'symbol':'600001','close':price})
        inputs['benchmarks'].extend([{'benchmark_id':key,'trade_date':day,'close':100+index*multiplier} for key,multiplier in [('csi_all_share',1),('csi_2000',2)]])
    return inputs


def test_portable_builder_preserves_calendar_group_scope_and_endpoints():
    data=build(synthetic_inputs());c=data['comparisons'][1]
    assert c['before']['days']==c['after']['days']==40
    assert c['before']['reference_change_pct']>0>c['after']['reference_change_pct']
    assert data['universe']['anchor_members']==1
    assert data['universe']['excluded_board_member_days']>0
    assert c['fixed_after']['covered']==1
    assert c['paired']['count']==1


def test_portable_builder_rejects_missing_current_membership_and_duplicate():
    inputs=synthetic_inputs()
    inputs['members']=[r for r in inputs['members'] if r['trade_date']!='2026-07-06']
    with pytest.raises(ValueError,match='missing historical membership'):build(inputs)
    inputs=synthetic_inputs();inputs['activities'].append(inputs['activities'][0])
    with pytest.raises(ValueError,match='duplicate source identity'):build(inputs)
