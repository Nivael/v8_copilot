from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from canonical_json import digest
from etf_issuer_nav import load_issuer_navs
from etf_nav_parsers import parse_efunds
from etf_nav_sources import reconcile_fund
from etf_nav_refresh import refresh_issuer_navs as real_refresh
from market_calendar import sessions_2026
from tests.etf_nav_fixtures import archive,refresh_issuer_navs

NOW=datetime(2026,11,5,tzinfo=timezone.utc)
CALENDAR=sessions_2026(date(2026,8,4),date(2026,11,4))
CODES=('510300.SH','510310.SH','510330.SH','159919.SZ','510500.SH','159922.SZ','512100.SH','159845.SZ')


class Complete:
    def get_navs(self,code,calendar):return [{'ts_code':code,'nav_date':d,'unit_nav':2} for d in calendar],[]


@pytest.fixture
def snapshot(tmp_path):
    assert refresh_issuer_navs(Complete(),through='2026-11-04',output=tmp_path,now=NOW)['status']=='complete'
    return tmp_path,json.loads((tmp_path/'current.json').read_text())


def save(folder,raw):
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'})
    (folder/'current.json').write_text(json.dumps(raw))


def update_source(folder,ref,change):
    path=folder/'responses'/(ref['response_sha256']+'.raw');raw=change(path.read_bytes())
    key=sha256(raw).hexdigest();(folder/'responses'/(key+'.raw')).write_bytes(raw)
    ref.update(response_sha256=key,bytes=len(raw))


def test_all_34_original_responses_and_488_exact_unit_NAVs_reconciled_readonly(snapshot):
    folder,raw=snapshot;before=(folder/'current.json').read_bytes();meta,rows=load_issuer_navs(folder,NOW);audit=meta['raw_reconciliation']
    assert len(rows)==8 and audit['source_response_count']==34 and audit['nav_observations']==488
    assert audit['snapshot_digest']==raw['content_digest'] and audit['exact_source_projection_verified'] is True
    for fund in audit['funds']:
        assert len(fund['records'])==61 and fund['unit']=='CNY_per_share'
        assert all(p['source_value']=='2' and p['raw_text']=='2' for p in fund['records'])
    assert all(audit[k] is False for k in ('historical_PIT','corporate_actions_checked','whole_fund_daily_scope_verified','share_precision_verified','final_revision_verified'))
    assert audit['estimated_net_subscription_yuan'] is None and (folder/'current.json').read_bytes()==before


@pytest.mark.parametrize('code',CODES)
@pytest.mark.parametrize('bad',['projection','raw_bytes','query','source_date'])
def test_each_fund_requires_original_projection_query_and_observation_binding_even_when_summary_rehashed(snapshot,code,bad):
    folder,raw=snapshot;ref=next(r for r in raw['responses'] if r['code']==code)
    if bad=='projection':raw['etf_navs'][code][0]['unit_nav']=3
    elif bad=='raw_bytes':(folder/'responses'/(ref['response_sha256']+'.raw')).write_bytes(b'changed')
    elif bad=='query':ref['url']=ref['url'].replace('https://','http://')
    else:
        for r in raw['responses']:
            if r['code']==code:r['observed_at']='2026-08-01T00:00:00+00:00'
    save(folder,raw);before=(folder/'current.json').read_bytes()
    assert load_issuer_navs(folder,NOW)==({'availability':'invalid'}, {})
    assert (folder/'current.json').read_bytes()==before


@pytest.mark.parametrize('bad',['missing','duplicate','foreign','method','bytes','naive','future','boolean_page'])
def test_missing_duplicate_foreign_or_mistimed_originals_cannot_reuse_stale_NAV(snapshot,bad):
    folder,raw=snapshot;ref=raw['responses'][0]
    if bad=='missing':raw['responses'].pop(0)
    elif bad=='duplicate':raw['responses'].insert(0,deepcopy(ref))
    elif bad=='foreign':ref['code']='000000.SH'
    elif bad=='method':ref['method']='POST'
    elif bad=='bytes':ref['bytes']+=1
    elif bad=='naive':ref['observed_at']='2026-11-05T00:00:00'
    elif bad=='future':ref['observed_at']='2026-11-06T00:00:00+00:00'
    else:next(r for r in raw['responses'] if r['code']=='510330.SH')['params']['pageIndex']=True
    save(folder,raw);assert load_issuer_navs(folder,NOW)==({'availability':'invalid'}, {})


@pytest.mark.parametrize('bad',['schema','unit_column','page_count','page_total','NF_boundary','NF_total','NF_instrument','raw_NAV','float_loss'])
def test_source_role_and_paging_changes_cannot_pass_after_rehashing_source_and_summary(snapshot,bad):
    folder,raw=snapshot
    code={'schema':'510310.SH','unit_column':'159919.SZ','page_count':'510330.SH','page_total':'510300.SH',
          'NF_boundary':'510500.SH','NF_total':'510500.SH','NF_instrument':'510500.SH','raw_NAV':'159919.SZ','float_loss':'510310.SH'}[bad]
    refs=[r for r in raw['responses'] if r['code']==code]
    if bad=='schema':ref=refs[1];change=lambda b:b.replace(b'2 Enum',b'3 Enum')
    elif bad=='unit_column':ref=refs[0];change=lambda b:b.replace('份额净值'.encode(),'累计净值'.encode())
    elif bad=='page_count':ref=refs[0];change=lambda b:b.replace(b"totalPage = '4'",b"totalPage = '3'")
    elif bad=='page_total':ref=refs[0];change=lambda b:b.replace(b'"totalCount": 61',b'"totalCount": 62')
    elif bad=='NF_boundary':raw['responses'].remove(refs[-1]);save(folder,raw);assert load_issuer_navs(folder,NOW)[0]['availability']=='invalid';return
    elif bad=='NF_total':ref=refs[0];ref['reported_history_total']=62;change=lambda b:b
    elif bad=='NF_instrument':ref=refs[0];change=lambda b:b.replace(b'"fundCode": null',b'"fundCode": "512100"')
    elif bad=='raw_NAV':ref=refs[0];change=lambda b:b.replace(b'<td>2</td>',b'<td>99</td>')
    else:
        ref=refs[2];change=lambda b:b.replace(b'_1_2_99_',b'_1_2.00000000000000000001_99_')
    update_source(folder,ref,change);save(folder,raw);assert load_issuer_navs(folder,NOW)[0]['availability']=='invalid'


def test_NF_history_totals_may_vary_outside_requested_window_without_fabricating_a_global_total(snapshot):
    folder,raw=snapshot;ref=next(r for r in raw['responses'] if r['code']=='510500.SH')
    def change(b):
        data=json.loads(b);data['data']['jjjzList']['total']=62;return json.dumps(data).encode()
    update_source(folder,ref,change);ref['reported_history_total']=62;save(folder,raw)
    assert load_issuer_navs(folder,NOW)[0]['availability']=='observed'


@pytest.mark.parametrize('code',['510300.SH','510500.SH'])
@pytest.mark.parametrize('page_value',[True,1.0])
def test_boolean_and_fractional_JSON_page_metadata_cannot_be_coerced_into_an_integer(snapshot,code,page_value):
    folder,raw=snapshot;ref=next(r for r in raw['responses'] if r['code']==code)
    def change(b):
        data=json.loads(b)
        if code=='510300.SH':data['currentPage']=page_value
        else:data['data']['jjjzList']['pageNum']=page_value
        return json.dumps(data).encode()
    update_source(folder,ref,change);save(folder,raw)
    assert load_issuer_navs(folder,NOW)[0]['availability']=='invalid'


def test_exact_parser_retains_trailing_zero_and_precision_without_evaluating_JavaScript():
    text='mk_510310_1y="0_1_2_3_4;20261104_1_2.00000000000000000001_99_0;";'
    point=parse_efunds(text,'510310.SH',CALENDAR,exact=True)[0]
    assert point['raw_text']=='2.00000000000000000001' and Decimal(point['source_value'])!=Decimal(str(2.0))
    with pytest.raises(ValueError):parse_efunds(text+'alert(1)','510310.SH',CALENDAR,exact=True)


def test_collector_cannot_publish_unbound_rows_or_repair_a_rehashed_staged_projection(snapshot):
    folder,raw=snapshot;before=(folder/'current.json').read_bytes()
    report=real_refresh(Complete(),through='2026-11-04',output=folder,now=NOW)
    assert report['status']=='failed' and report['current_snapshot_preserved'] and (folder/'current.json').read_bytes()==before
    stage=folder/'staging/2026-11-04-61/510300.SH.json';staged=json.loads(stage.read_text());staged['rows'][0]['unit_nav']=3
    staged['content_digest']=digest({k:v for k,v in staged.items() if k!='content_digest'});stage.write_text(json.dumps(staged))
    calls=[]
    class Repair(Complete):
        def get_navs(self,code,calendar):calls.append(code);return super().get_navs(code,calendar)
    report=refresh_issuer_navs(Repair(),through='2026-11-04',output=folder,now=NOW,repair=True)
    assert report['status']=='complete' and report['reused_series']==7 and calls==['510300.SH']


def test_live_collection_can_observe_responses_after_its_start(monkeypatch,tmp_path):
    import etf_nav_refresh as module
    class Clock:
        calls=0
        @classmethod
        def now(cls,*a):cls.calls+=1;return NOW if cls.calls==1 else NOW+timedelta(seconds=2)
    monkeypatch.setattr(module,'datetime',Clock)
    class Live(Complete):
        def get_navs(self,code,calendar):
            rows,_=super().get_navs(code,calendar)
            return rows,archive(tmp_path,code,calendar,rows,NOW+timedelta(seconds=1))
    report=real_refresh(Live(),through='2026-11-04',output=tmp_path)
    assert report['status']=='complete' and report['nav_observations']==488
    assert load_issuer_navs(tmp_path,NOW+timedelta(seconds=3))[0]['availability']=='observed'


def test_source_changed_after_an_earlier_fund_was_checked_cannot_replace_current(snapshot):
    folder,raw=snapshot;before=(folder/'current.json').read_bytes()
    class Racing(Complete):
        def get_navs(self,code,calendar):
            rows,_=super().get_navs(code,calendar);refs=archive(folder,code,calendar,rows,NOW)
            if code==CODES[-1]:
                first=next(r for r in raw['responses'] if r['code']==CODES[0])
                (folder/'responses'/(first['response_sha256']+'.raw')).write_bytes(b'changed during collection')
            return rows,refs
    report=real_refresh(Racing(),through='2026-11-04',output=folder,now=NOW)
    assert report['status']=='failed' and report['current_snapshot_preserved'] and (folder/'current.json').read_bytes()==before


def test_invalid_NAV_source_cannot_retain_panel_NAV_coverage(tmp_path):
    from market_risk import build_market_risk_status,market_update_status
    folder=tmp_path/'issuer_nav'
    refresh_issuer_navs(Complete(),through='2026-11-04',output=folder,now=NOW)
    raw=json.loads((folder/'current.json').read_text());raw['etf_navs']['510310.SH'][0]['unit_nav']=3;save(folder,raw)
    market=build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'absent.db',manifest_path=tmp_path/'absent.json',now=NOW)
    assert market['issuer_nav_snapshot']=={'availability':'invalid'}
    assert all(row['nav_observed_etfs']==0 and row['estimated_net_subscription_yuan'] is None for row in market['etf_aggregate'].values())
    source=next(row for row in market_update_status(snapshot_dir=tmp_path,now=NOW) if row['source_id']=='issuer_etf_nav')
    assert source['availability']=='invalid' and source['observation_count'] is None and source['series_at_target'] is None
