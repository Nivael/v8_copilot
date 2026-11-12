from copy import deepcopy
from datetime import date
from hashlib import sha256

import pytest

import broad_fund_evidence as b
from market_calendar import sessions_2026


def fixture():
    page='报告期内单一投资者持有基金份额比例达到或超过20%的情况 联接基金 2,000.00 100.00 378.00 1,722.00 17.22%'
    entry={'code':'510310.SH','holder_kind':'feeder_fund','holder_label':'联接基金',
           'period_start':'2026-07-01','period_end':'2026-09-30','proof_pages':[1],
           'page_sha256':{'1':sha256(page.encode()).hexdigest()},'opening_shares':'2000.00',
           'increased_shares':'100.00','decreased_shares':'378.00','closing_shares':'1722.00','closing_share_pct':'17.22'}
    report={'code':'510310.SH','period_start':'2026-07-01','period_end':'2026-09-30','closing_shares':'10000.00',
            'publication_date':'2026-10-27','pdf_url':'https://www.sse.com.cn/report.pdf'}
    return entry,[page],report


def test_disclosed_holding_change_is_not_filtered_by_period_end_20pct_or_called_net_subscription():
    entry,pages,report=fixture();before=deepcopy(entry)
    row=b.holder_row(entry,pages,report)
    assert row['holding_change_shares']=='-278.00' and row['closing_share_pct']=='17.22'
    assert row['sources'][0]['url'].endswith('#page=1')
    assert not any('subscription' in key or 'cash' in key for key in row)
    assert entry==before


@pytest.mark.parametrize('change',['text','page','page_digest','code','period','balance','pct','invented_holder','wrong_kind','source_number','number_type','swapped_fields'])
def test_changed_holder_identity_pages_numbers_or_period_cannot_survive_review(change):
    entry,pages,report=fixture()
    if change=='text':pages[0]+=' changed'
    elif change=='page':entry['proof_pages']=[2]
    elif change=='page_digest':entry['page_sha256']['1']='0'*64
    elif change=='code':entry['code']='510300.SH'
    elif change=='period':entry['period_end']='2026-06-30'
    elif change=='balance':entry['closing_shares']='1721.00'
    elif change=='pct':entry['closing_share_pct']='17.23'
    elif change=='invented_holder':entry['holder_label']='中央汇金联接基金'
    elif change=='wrong_kind':entry['holder_kind']='national_team'
    elif change=='number_type':entry['opening_shares']=2000.0
    elif change=='swapped_fields':entry['opening_shares'],entry['increased_shares']=entry['increased_shares'],entry['opening_shares']
    else:
        entry['opening_shares']='1999.00';entry['increased_shares']='101.00'
    with pytest.raises(ValueError):b.holder_row(entry,pages,report)


def test_no_threshold_disclosure_does_not_create_zero_huijin_or_insurer_holdings():
    entry,pages,report=fixture()
    pages=['报告期内单一投资者持有基金份额比例达到或超过20%的情况 本报告期内未有单一投资者持有基金份额比例达到或超过20%的情况。']
    entry.update(holder_kind='no_20pct_holder_reported',page_sha256={'1':sha256(pages[0].encode()).hexdigest()})
    row=b.holder_row(entry,pages,report)
    assert row['kind']=='no_20pct_holder_reported' and 'closing_shares' not in row and 'holder_label' not in row
    pages[0]='报告期内单一投资者持有基金份额比例达到或超过20%的情况 未找到数据'
    entry['page_sha256']['1']=sha256(pages[0].encode()).hexdigest()
    with pytest.raises(ValueError):b.holder_row(entry,pages,report)


def nav_fixture(monkeypatch, *, definitions=b.NAV_DEFINITIONS, share_change=-2, direction=1):
    dates=sessions_2026(date(2026,10,1),date(2026,11,6))[-21:]
    source={code:[{'nav_date':day,'unit_nav':1+direction*i/100} for i,day in enumerate(dates)] for code in definitions}
    reconciled=[{'code':code,'records':[{'date':day,'source_value':f'{1+direction*i/100:.4f}'} for i,day in enumerate(dates)]} for code in source]
    meta={'availability':'observed','through':'2026-11-06','fetched_at':'2026-11-07T00:00:00+08:00',
          'calendar':dates,'content_digest':'0'*64,'raw_reconciliation':{'funds':reconciled}}
    monkeypatch.setattr(b,'load_issuer_navs',lambda *args:(meta,source))
    broad={'as_of':'2026-11-06','groups':[{'funds':[{'code':code,'five_day_share_change_pct':share_change} for code in source]}]}
    return broad,meta,source


def test_nav_has_its_own_exact_dates_and_source_decimals_and_never_publishes_cash(monkeypatch):
    broad,meta,source=nav_fixture(monkeypatch)
    result=b.navs(broad);row=result['rows'][0]
    assert result['availability']=='available' and result['observed_funds']==8 and result['sessions']==21
    assert row['unit_nav']=='1.2000'
    assert row['five_day_nav_anchor']==meta['calendar'][-6] and row['twenty_day_nav_anchor']==meta['calendar'][0]
    assert row['five_day_nav_change_pct']==pytest.approx((1.2/1.15-1)*100)
    assert row['twenty_day_nav_change_pct']==pytest.approx(20)
    assert row['five_day_share_change_pct']==-2
    assert not any('cash' in key or 'subscription' in key for key in result)
    assert source[next(iter(source))][-1]['nav_date']=='2026-11-06'


@pytest.mark.parametrize('change',['source_failure','target_mismatch','missing_fund','missing_exact_value'])
def test_incomplete_or_mismatched_nav_does_not_label_old_values_as_current(monkeypatch,change):
    broad,meta,source=nav_fixture(monkeypatch)
    if change=='source_failure':meta['availability']='invalid'
    elif change=='target_mismatch':meta['through']='2026-11-05'
    elif change=='missing_fund':broad['groups'][0]['funds'].pop()
    else:meta['raw_reconciliation']['funds'][0]['records'].pop()
    assert b.navs(broad)=={'availability':'unavailable'}


def test_quarter_publication_after_market_date_is_not_backfilled_as_known(monkeypatch):
    monkeypatch.setattr(b,'holders',lambda *args,**kwargs:{'availability':'available','rows':[{'published_on':'2026-10-27'}]})
    monkeypatch.setattr(b,'navs',lambda *args,**kwargs:{'availability':'unavailable'})
    assert b.reading({'as_of':'2026-10-26'})['holders']=={'availability':'unavailable'}
    assert b.reading({'as_of':'2026-10-27'})['holders']['availability']=='available'


def test_missing_review_and_nav_do_not_create_a_false_empty_market_reading(tmp_path):
    result=b.reading({'as_of':'2026-11-06'},directory=tmp_path,announcement_root=tmp_path/'none')
    assert result=={'unit_nav':{'availability':'unavailable'},'holders':{'availability':'unavailable'}}
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('shares,direction,headline', [
    (2,1,'12只样本近5日份额和净值都回升'),
    (2,-1,'12只样本份额都增加，净值却仍下跌'),
    (-2,-1,'12只样本份额与净值同步回落'),
    (0,0,'近5日：0只份额增加、0只减少，0只净值回升'),
])
def test_complete_broad_samples_get_directional_conclusion_without_named_buyer(shares,direction,headline,monkeypatch):
    broad,_,_=nav_fixture(monkeypatch,definitions=b.BROAD_NAV_DEFINITIONS,share_change=shares,direction=direction)
    result=b.navs(broad)
    assert result['observed_funds']==result['sample_funds']==12 and result['headline']==headline
    assert '单位净值按公布值计算' in result['basis_note']
    if direction<0:assert '12只近20日净值仍下跌' in result['interpretation'] and '短反弹' not in result['interpretation']
    assert not any(key in result for key in ('national_team','insurance','estimated_net_subscription_yuan'))


@pytest.mark.parametrize('shares',[True,float('nan'),float('inf'),None,'invalid'])
def test_missing_or_invalid_share_comparison_cannot_create_a_combined_conclusion(shares,monkeypatch):
    broad,_,_=nav_fixture(monkeypatch,share_change=shares)
    assert b.navs(broad)=={'availability':'unavailable'}
