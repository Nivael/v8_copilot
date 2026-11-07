from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
from urllib.parse import urlencode

import pytest

from canonical_json import digest
import etf_daily_sources as m
from etf_public_refresh import refresh_public_etfs as unbound_refresh
from etf_source_fixtures import refresh_public_etfs, refresh_szse_etfs
from market_calendar import sessions_2026
from market_risk import _public_etfs, _szse_etfs, build_market_risk_status

NOW=datetime(2026,11,5,tzinfo=timezone.utc)
CALENDAR=sessions_2026(date(2026,9,30),date(2026,11,4))


class SSE:
    def get_day(self,day):return [{'ts_code':c,'trade_date':day,'fd_share':1234.56} for c in m.SSE_CODES],[]


class SZSE:
    def get_history(self,code,calendar,*,nav=False):
        return [{'ts_code':code,'nav_date' if nav else 'trade_date':day,'unit_nav' if nav else 'fd_share':4.1234 if nav else 1234.56}
                for day in (calendar[-11:-1] if nav else calendar)],[]


@pytest.fixture(params=['SSE','SZSE'])
def capture(tmp_path,request):
    venue=request.param;folder=tmp_path/('public_etf' if venue=='SSE' else 'public_etf_szse')
    (refresh_public_etfs if venue=='SSE' else refresh_szse_etfs)(SSE() if venue=='SSE' else SZSE(),through='2026-11-04',output=folder,now=NOW)
    raw=json.loads((folder/'current.json').read_text())
    return venue,folder,raw


def check(capture):
    venue,folder,raw=capture
    return (m.reconcile_sse if venue=='SSE' else m.reconcile_szse)(folder,raw,NOW)


def save_payload(folder,ref,payload):
    data=json.dumps(payload,ensure_ascii=False).encode();key=hashlib.sha256(data).hexdigest();(folder/'responses'/(key+'.json')).write_bytes(data);ref['response_sha256']=key


def test_source_text_and_decimal_scaling_are_separate_from_rounding_scope_cash_and_revisions(capture):
    data=check(capture);assert data['share_observations']==(105 if capture[0]=='SSE' else 63)
    assert data['nav_observations']==(0 if capture[0]=='SSE' else 30)
    p=data['funds'][0]['records'][0];assert (p['raw_text'],p['ten_thousand_shares'],p['shares'],p['fractional_digits'])==('1234.56','1234.56','12345600.00',2)
    assert data['exact_source_projection_verified'] is True and data['estimated_net_subscription_yuan'] is None
    assert all(data[k] is False for k in ('whole_fund_daily_scope_verified','source_rounding_rule_verified','share_precision_verified','final_revision_verified','corporate_actions_checked'))


@pytest.mark.parametrize('bad',['bytes','missing_file','missing_ref','duplicate_ref','query_code','query_date','query_page','snapshot_value','snapshot_date','snapshot_duplicate','snapshot_code','future_time','before_source_date','wrong_unit_or_query','record_count','page_count','fractional_count','duplicate_source','source_code','source_date','source_value','ambiguous_decimal','bool_value'])
def test_changed_raw_or_projection_cannot_be_read_as_verified_even_after_metadata_rehash(capture,bad):
    venue,folder,raw=capture;ref=raw['responses'][0];path=folder/'responses'/(ref['response_sha256']+'.json');payload=json.loads(path.read_text())
    code=(m.SSE_CODES if venue=='SSE' else m.SZSE_CODES)[0];p=raw['etf_shares'][code][0]
    if bad=='bytes':path.write_bytes(b'changed')
    elif bad=='missing_file':path.rename(path.with_suffix('.moved'))
    elif bad=='missing_ref':raw['responses'].pop(0)
    elif bad=='duplicate_ref':raw['responses'].append(deepcopy(ref))
    elif bad=='query_code':ref['url']+='&code=999999'
    elif bad=='query_date':ref['url']=ref['url'].replace('2026-09-30','2026-09-29')
    elif bad=='query_page':ref['page']=2
    elif bad=='snapshot_value':p['fd_share']=1234.57
    elif bad=='snapshot_date':p['trade_date']='2026-09-29'
    elif bad=='snapshot_duplicate':raw['etf_shares'][code].append(deepcopy(p))
    elif bad=='snapshot_code':p['ts_code']='999999.SH'
    elif bad=='future_time':ref['observed_at']='2026-11-06T00:00:00+00:00'
    elif bad=='before_source_date':ref['observed_at']='2026-09-29T00:00:00+00:00'
    else:
        meta=payload['pageHelp'] if venue=='SSE' else payload[0]['metadata'];records=payload['result'] if venue=='SSE' else payload[0]['data'];record=records[0]
        field='TOT_VOL' if venue=='SSE' else 'current_size';code_field='SEC_CODE' if venue=='SSE' else 'fund_code';day_field='STAT_DATE' if venue=='SSE' else 'size_date'
        if bad=='wrong_unit_or_query':
            if venue=='SSE':payload['sqlId']='AUM_QUERY'
            else:meta['cols']['current_size']='基金规模(亿元)'
        elif bad=='record_count':meta['total' if venue=='SSE' else 'recordcount']+=1
        elif bad=='page_count':meta['pageCount' if venue=='SSE' else 'pagecount']+=1
        elif bad=='fractional_count':meta['total' if venue=='SSE' else 'recordcount']=True
        elif bad=='duplicate_source':records.append(deepcopy(record))
        elif bad=='source_code':record[code_field]='999999'
        elif bad=='source_date':record[day_field]='2026-10-01'
        elif bad=='source_value':record[field]='1234.57'
        elif bad=='ambiguous_decimal':record[field]='1,23,4.56'
        else:record[field]=True
        save_payload(folder,ref,payload)
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});(folder/'current.json').write_text(json.dumps(raw))
    with pytest.raises((OSError,ValueError,KeyError)):check(capture)
    state,rows=(_public_etfs if venue=='SSE' else _szse_etfs)(folder,NOW)
    assert state['availability']=='invalid' and rows==[] and 'raw_reconciliation' not in state


def test_unbound_normalized_values_are_not_a_source_archive(tmp_path):
    unbound_refresh(SSE(),through='2026-11-04',output=tmp_path/'public_etf',now=NOW)
    assert _public_etfs(tmp_path/'public_etf',NOW)[0]['availability']=='invalid'
    data=build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'none.db',manifest_path=tmp_path/'none.json',now=NOW)
    assert data['etfs']==[] and data['etf_aggregate']['5']['observed_etfs']==0


def test_decimal_reconciliation_rejects_float_loss_and_preserves_literal_trailing_zeroes(tmp_path):
    # A source value below float resolution must not silently round into its cached projection.
    rows=[{'ts_code':c,'trade_date':d,'fd_share':1234.56} for d in CALENDAR for c in m.SSE_CODES]
    query={'sqlId':m.SSE_SQL,'isPagination':'true','STAT_DATE':CALENDAR[0],'pageHelp.pageSize':'1000','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.endPage':'1','pageHelp.cacheSize':'1'}
    (tmp_path/'responses').mkdir()
    ref={'query_date':CALENDAR[0],'page':1,'url':m.SSE_API+'?'+urlencode(query),'complete_daily_rows':5,'observed_at':NOW.isoformat()}
    payload={'sqlId':m.SSE_SQL,'result':[{'SEC_CODE':c[:6],'STAT_DATE':CALENDAR[0],'TOT_VOL':'1234.5600'} for c in m.SSE_CODES],
             'pageHelp':{'total':5,'pageNo':1,'pageCount':1}}
    raw={'calendar':CALENDAR,'requested_through':CALENDAR[-1],'content_digest':'test','responses':[ref],
         'etf_shares':{c:[r for r in rows if r['ts_code']==c and r['trade_date']==CALENDAR[0]] for c in m.SSE_CODES}}
    save_payload(tmp_path,ref,payload);data=m.reconcile_sse(tmp_path,raw,NOW)
    assert data['funds'][0]['records'][0]['raw_text']=='1234.5600' and data['funds'][0]['fractional_digit_counts']=={4:1}
    payload['result'][0]['TOT_VOL']='1234.560000000000000001';save_payload(tmp_path,ref,payload)
    with pytest.raises(ValueError,match='exact source decimals'):m.reconcile_sse(tmp_path,raw,NOW)


def test_repair_will_not_reuse_a_snapshot_whose_raw_response_changed(tmp_path):
    output=tmp_path/'public_etf';refresh_public_etfs(SSE(),through='2026-11-04',output=output,now=NOW)
    raw=json.loads((output/'current.json').read_text());path=output/'current.json';before=path.read_bytes()
    (output/'responses'/(raw['responses'][0]['response_sha256']+'.json')).write_bytes(b'changed')
    with pytest.raises(ValueError,match='verified public snapshot'):refresh_public_etfs(SSE(),through='2026-11-04',output=output,now=NOW,repair_missing=True)
    assert path.read_bytes()==before


def test_reader_is_offline_and_preserves_all_source_and_current_bytes(capture,monkeypatch):
    _,folder,_=capture;before={str(p):p.read_bytes() for p in folder.rglob('*.json')}
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:pytest.fail('GET attempted network'))
    meta,rows=(_public_etfs if capture[0]=='SSE' else _szse_etfs)(folder,NOW)
    assert meta['availability']=='observed' and rows and before=={str(p):p.read_bytes() for p in folder.rglob('*.json')}


@pytest.mark.parametrize('bad',['NAV_bytes','NAV_unit','NAV_date','NAV_code','normalized_NAV'])
def test_bad_NAV_source_cannot_leave_the_same_snapshot_share_path_certified(tmp_path,bad):
    folder=tmp_path/'public_etf_szse';refresh_szse_etfs(SZSE(),through='2026-11-04',output=folder,now=NOW)
    raw=json.loads((folder/'current.json').read_text());ref=next(r for r in raw['responses'] if r['kind']=='NAV')
    path=folder/'responses'/(ref['response_sha256']+'.json');payload=json.loads(path.read_text())
    if bad=='NAV_bytes':path.write_bytes(b'changed')
    elif bad=='normalized_NAV':raw['etf_navs'][ref['code']][0]['unit_nav']=4.9999
    else:
        if bad=='NAV_unit':payload[0]['metadata']['cols']['nav_per_share']='单位基金净值(万元)'
        elif bad=='NAV_date':payload[0]['data'][0]['nav_date']=payload[0]['data'][1]['nav_date']
        else:payload[0]['data'][0]['fund_code']='159999'
        save_payload(folder,ref,payload)
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});(folder/'current.json').write_text(json.dumps(raw));before=(folder/'current.json').read_bytes()
    meta,rows=_szse_etfs(folder,NOW)
    assert meta['availability']=='invalid' and rows==[] and before==(folder/'current.json').read_bytes()
