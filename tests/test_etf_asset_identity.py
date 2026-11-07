from copy import deepcopy
from datetime import datetime,timezone

import pytest

from etf_asset_identity import identity_status,parse_asset_disclosure

NOW=datetime(2026,11,5,tzinfo=timezone.utc)
REF={'url':'https://www.efunds.com.cn/fund/510310.shtml','response_sha256':'original-asset','observed_at':NOW.isoformat()}
PAGE='''<html><script>var fundCode="510310";</script><div id="ov-asset">517.89</div>
<div id="net-today">9.9999</div><span class="nav-update">2026-11-05</span>
<table><tr><td>基金规模:</td><td id="baseinfoAsset">数据截至2026-11-04：105,063,783,479.60元</td></tr></table>
<script>三个要素均为整个基金（不区分份额）层面数据。</script><div class="assetTotalMoney">总资产0元</div></html>'''


def inputs():
    asset=parse_asset_disclosure(PAGE,REF,NOW)
    nav={'date':'2026-11-04','source_value':'4.0609','source_url':'https://cdn.efunds.com.cn/market/2.0/510310_1y.js','response_sha256':'nav-proof','observed_at':NOW.isoformat()}
    share={'date':'2026-11-04','source_value':'2587204.4','shares':'25872044000.0','source_url':'https://query.sse.com.cn/source','response_sha256':'share-proof','observed_at':NOW.isoformat()}
    issuer={'availability':'observed','content_digest':'issuer','raw_reconciliation':{'availability':'source_reconciled','exact_source_projection_verified':True,'snapshot_digest':'issuer',
        'funds':[{'code':'510310.SH','unit':'CNY_per_share','asset_disclosure':asset,'records':[nav]}]}}
    sse={'availability':'observed','content_digest':'sse','raw_reconciliation':{'availability':'source_reconciled','exact_source_projection_verified':True,'snapshot_digest':'sse',
        'funds':[{'code':'510310.SH','share_unit':'ten_thousand_shares','records':[share]}]}}
    return issuer,sse


def test_only_the_specific_asset_field_and_its_own_date_are_read_not_latest_NAV_quarterly_scale_or_zero_placeholder():
    r=parse_asset_disclosure(PAGE,REF,NOW)
    assert r['asset_asof']=='2026-11-04' and r['asset_yuan']=='105063783479.60'
    assert r['raw_amount_text']=='105,063,783,479.60' and r['scope']=='site_states_whole_fund_net_assets'
    assert r['response_sha256']==REF['response_sha256'] and r['asset_rounding_rule_verified'] is False


@pytest.mark.parametrize('bad',['code','scope','unit','future_date','malformed_date','zero','duplicate','naive','future_observed'])
def test_unbound_or_mistyped_asset_identity_and_date_roles_are_not_certified(bad):
    page=PAGE;ref=deepcopy(REF)
    if bad=='code':page=page.replace('510310','510300')
    elif bad=='scope':page=page.replace('整个基金','部分份额')
    elif bad=='unit':page=page.replace('479.60元','479.60亿元')
    elif bad=='future_date':page=page.replace('数据截至2026-11-04','数据截至2026-11-06')
    elif bad=='malformed_date':page=page.replace('数据截至2026-11-04','数据截至2026-11-44')
    elif bad=='zero':page=page.replace('105,063,783,479.60','0')
    elif bad=='duplicate':page=page.replace('</table>','<td id="baseinfoAsset">数据截至2026-11-04：1元</td></table>')
    elif bad=='naive':ref['observed_at']='2026-11-05T00:00:00'
    else:ref['observed_at']='2026-11-06T00:00:00+00:00'
    assert parse_asset_disclosure(page,ref,NOW)=={'availability':'invalid','code':'510310.SH'}


def test_absent_optional_asset_does_not_certify_an_asset_value_or_break_an_otherwise_valid_NAV_source():
    assert parse_asset_disclosure('<html>no asset disclosure</html>',REF,NOW)=={'availability':'missing','code':'510310.SH'}
    issuer,sse=inputs();issuer['raw_reconciliation']['funds'][0]['asset_disclosure']={'availability':'missing','code':'510310.SH'}
    result=identity_status(issuer,sse,'2026-11-04')
    assert result['availability']=='missing' and result['disclosed_points'] is None and 'difference_yuan' not in result


def test_HTML_comments_are_not_an_active_asset_field_and_inline_markup_is_read_as_text():
    cell='<td id="baseinfoAsset">数据截至2026-11-04：105,063,783,479.60元</td>'
    assert parse_asset_disclosure(PAGE.replace(cell,'<!--'+cell+'-->'),REF,NOW)['availability']=='missing'
    assert parse_asset_disclosure(PAGE.replace('105,063,783,479.60','<span>105,063,783,479.60</span>'),REF,NOW)['asset_yuan']=='105063783479.60'


def test_exact_published_identity_is_one_point_not_independent_scope_or_zero_off_exchange_shares():
    result=identity_status(*inputs(),'2026-11-04')
    assert result['availability']=='arithmetic_compared' and result['disclosed_points']==result['compared_points']==1
    assert result['published_shares']=='25872044000.0' and result['unit_nav']=='4.0609'
    assert result['shares_times_unit_nav_yuan']=='105063783479.60000' and result['difference_yuan']=='0.00000'
    assert result['relation']=='equal_as_published' and result['matches_market_target'] is True
    assert result['source_independence_verified'] is result['whole_fund_daily_scope_verified'] is result['historical_PIT'] is False
    assert result['off_exchange_shares'] is result['full_fund_daily_shares'] is result['estimated_net_subscription_yuan'] is None


@pytest.mark.parametrize('difference',['105063783479.59','105063783479.61'])
def test_nonzero_identity_difference_is_not_positive_or_negative_subscription_flow(difference):
    issuer,sse=inputs();issuer['raw_reconciliation']['funds'][0]['asset_disclosure']['asset_yuan']=difference
    result=identity_status(issuer,sse,'2026-11-04')
    assert result['relation']=='different_as_published' and result['estimated_net_subscription_yuan'] is None
    assert result['off_exchange_shares'] is None


@pytest.mark.parametrize('bad',['issuer','issuer_flag','issuer_digest','share','share_flag','share_digest','unit_NAV','share_unit','duplicate_NAV','duplicate_share','conversion','asset_scope'])
def test_source_status_bindings_units_and_same_day_uniqueness_are_required(bad):
    issuer,sse=inputs();fund=issuer['raw_reconciliation']['funds'][0];shares=sse['raw_reconciliation']['funds'][0]
    if bad=='issuer':issuer['availability']='invalid'
    elif bad=='issuer_flag':issuer['raw_reconciliation']['exact_source_projection_verified']=False
    elif bad=='issuer_digest':issuer['content_digest']='other'
    elif bad=='share':sse['availability']='invalid'
    elif bad=='share_flag':sse['raw_reconciliation']['exact_source_projection_verified']=False
    elif bad=='share_digest':sse['content_digest']='other'
    elif bad=='unit_NAV':fund['unit']='asset_NAV'
    elif bad=='share_unit':shares['share_unit']='fund_share'
    elif bad=='duplicate_NAV':fund['records']*=2
    elif bad=='duplicate_share':shares['records']*=2
    elif bad=='conversion':shares['records'][0]['shares']='2587204.4'
    else:fund['asset_disclosure']['scope']='unknown'
    result=identity_status(issuer,sse,'2026-11-04')
    assert result['availability']!='arithmetic_compared' and 'difference_yuan' not in result
    assert result['off_exchange_shares'] is None and result['source_independence_verified'] is False


@pytest.mark.parametrize('missing',['NAV','share'])
def test_latest_or_nearest_date_cannot_replace_the_actual_asset_date(missing):
    issuer,sse=inputs();rows=issuer['raw_reconciliation']['funds'][0]['records'] if missing=='NAV' else sse['raw_reconciliation']['funds'][0]['records']
    rows[0]['date']='2026-11-05'
    result=identity_status(issuer,sse,'2026-11-04')
    assert result['availability']=='asset_only' and result['disclosed_points']==1 and result['compared_points']==0
    assert 'difference_yuan' not in result


def test_old_point_is_explicit_and_does_not_advance_market_target_coverage():
    result=identity_status(*inputs(),'2026-11-05')
    assert result['availability']=='arithmetic_compared' and result['matches_market_target'] is False
    assert result['date']=='2026-11-04'


def test_learning_point_count_is_not_daily_or_eight_fund_coverage(tmp_path,monkeypatch):
    import market_risk
    issuer,sse=inputs();result=identity_status(issuer,sse,'2026-11-04')
    monkeypatch.setattr(market_risk,'asset_identity_status',lambda *a:deepcopy(result))
    row=next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path,now=NOW) if r['source_id']=='etf_asset_identity')
    assert row['observation_count']==1 and row['observation_unit']=='披露时点' and row['declared_series']==1
    assert row['observed_source_groups']==1 and row['series_at_target'] is None and row['requested_through'] is None
    assert row['date_basis']=='asset_disclosure' and row['observed_through_min']=='2026-11-04'
