from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
import pytest

from canonical_json import digest
from data_refresh import atomic_write_json,TUSHARE_ROW_SOURCE
from market_calendar import sessions_2026
import research_history_bse as bse
from research_history_price_chain import validate_price_packet


def seal(value):
    value['content_digest']=digest({k:v for k,v in value.items() if k!='content_digest'});return value


def fixture(root,change=None,calendar=None):
    calendar=calendar or sessions_2026(date(2026,5,6),date(2026,6,26))
    days=calendar[2:];values={d:round(2+i/100,2) for i,d in enumerate(days)};name='*ST田野';symbol='920023.BJ'
    prices={'rc':0,'data':{'market':0,'code':'920023','name':name,'klines':[f'{d},{v},{v},{v+.01:.2f},{v-.01:.2f},100,200,1,0,0,1' for d,v in values.items()]}}
    following=sessions_2026(date.fromisoformat(days[-1])+timedelta(days=1),date.fromisoformat(days[-1])+timedelta(days=15))[0]
    quote=['']*31;quote[:5]=['62',name,'920023','2.90',str(values[days[-1]])];quote[30]=following.replace('-','')+'150000'
    quotes={'code':0,'data':{'bj920023':{'qt':{'bj920023':quote}}}}
    stamp=datetime.now(timezone.utc).isoformat();rows=[{'symbol':'920023','trade_date':d,'close':v,'volume':100,'source':TUSHARE_ROW_SOURCE} for d,v in list(values.items())[:25]]
    if change=='foreign_code':prices['data']['code']='000016'
    elif change=='foreign_market':prices['data']['market']=1
    elif change=='price_error':prices['rc']=1
    elif change=='missing_day':prices['data']['klines'].pop(4)
    elif change=='duplicate_day':prices['data']['klines'].insert(4,prices['data']['klines'][3])
    elif change=='nonfinite':prices['data']['klines'][4]=prices['data']['klines'][4].replace(',2.04,',',NaN,',1)
    elif change=='bad_decimal':prices['data']['klines'][4]=prices['data']['klines'][4].replace(',2.04,',',broken,',1)
    elif change=='zero_volume':prices['data']['klines'][4]=prices['data']['klines'][4].replace(',100,200,',',0,200,')
    elif change=='wrong_range':prices['data']['klines'][4]=prices['data']['klines'][4].replace(',2.03,',',3.03,')
    elif change=='extra_column':prices['data']['klines'][4]+=',100'
    elif change=='wrong_quote_code':quote[2]='000016'
    elif change=='wrong_quote_market':quote[0]='51'
    elif change=='wrong_quote_name':quote[1]='其他公司'
    elif change=='quote_error':quotes['code']=1
    elif change=='missing_quote':quotes['data']={}
    elif change=='quote_not_next_session':quote[30]=days[-1].replace('-','')+'150000'
    elif change=='quote_future':quote[30]='20991231150000'
    elif change=='endpoint_mismatch':quote[4]='9.90'
    elif change=='archive_price':rows[5]['close']=99
    elif change=='archive_provider':rows[5]['source']='unidentified'
    elif change=='too_few_archive':rows=rows[:19]
    elif change=='duplicate_archive':rows[5]=deepcopy(rows[4])
    archive=seal({'version':'fixture_archive_v1','observed_at':stamp,'rows':rows});atomic_write_json(root/'inputs/historical_prices.json',archive)
    folder=root/'inputs/bse_vendor_v1';folder.mkdir(parents=True,exist_ok=True)
    def raw(value,url):
        body=json.dumps(value,ensure_ascii=False).encode();key=sha256(body).hexdigest();(folder/(key+'.json')).write_bytes(body)
        return {'url':url,'response_url':url,'sha256':key,'bytes':len(body),'observed_at':stamp}
    price=raw(prices,bse.price_url(symbol,days[0],days[-1]));quoted=raw(quotes,bse.quote_url(symbol,days[0],days[-1]))
    if change=='foreign_host':price['url']=price['response_url']=price['url'].replace('push2his.eastmoney.com','example.org')
    elif change=='unadjusted':price['url']=price['response_url']=price['url'].replace('fqt=1','fqt=0')
    elif change=='naive_clock':price['observed_at']='2026-07-01T00:00:00'
    elif change=='future_clock':price['observed_at']='2099-01-01T00:00:00+00:00'
    elif change=='premature_clock':price['observed_at']='2026-01-01T00:00:00+00:00'
    elif change=='changed_bytes':(folder/(price['sha256']+'.json')).write_text('{}')
    elif change=='symlink':
        original=folder/(price['sha256']+'.json');other=folder/'mutable.json';original.rename(other);original.symlink_to(other)
    source=seal({'version':bse.SOURCE_VERSION,'symbol':symbol,'start':days[0],'through':days[-1],
                 'comparison_basis':'vendor_qfq_with_archived_tushare_and_next_session_quote','official_daily_crosscheck':False,
                 'archive_digest':archive['content_digest'],'prices':price,'quote':quoted})
    if change=='promoted_official':source['official_daily_crosscheck']=True;seal(source)
    atomic_write_json(folder/(source['content_digest']+'.json'),source)
    return calendar,source,folder


def base_packet(root,calendar):
    import research_history_prices
    points=[{'date':d,'value':10.,'level':100.,'basis':'historical_qfq'} for d in calendar]
    packet=seal({'version':'research_history_paths_v1','processor_digest':sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest(),
                 'data':{'calendar':calendar,'stocks':{'000001.SZ':{'name':'原标的','points':points,'as_of':calendar[-1]}},'market':deepcopy(points),'st':deepcopy(points),'source_digests':{'old':'a'*64}}})
    atomic_write_json(root/'price_paths/history'/(packet['content_digest']+'.json'),packet);return packet


def test_bse_profile_uses_explicit_vendor_basis_preserves_missing_prefix_and_is_idempotent(tmp_path):
    calendar,source,_=fixture(tmp_path);base=base_packet(tmp_path,calendar);before=deepcopy(base)
    stock,_,checks=bse.source_stock(tmp_path,source['content_digest'],calendar)
    assert all(p['value'] is None for p in stock['points'][:2]) and all(p['level'] is not None for p in stock['points'][2:])
    assert checks['archive_close_checks']==25 and checks['official_daily_crosscheck'] is False
    assert stock['history_source_kind']=='eastmoney_bse_qfq_v1' and '东方财富' in stock['price_basis_note']
    packet=bse.extension_packet(base,source['content_digest'],root=tmp_path);validate_price_packet(packet,root=tmp_path)
    assert base==before and packet['data']['stocks']['000001.SZ']==base['data']['stocks']['000001.SZ']
    atomic_write_json(tmp_path/'price_paths/history'/(packet['content_digest']+'.json'),packet)
    assert bse.extension_packet(packet,source['content_digest'],root=tmp_path)==packet


@pytest.mark.parametrize('change',['foreign_code','foreign_market','price_error','missing_day','duplicate_day','nonfinite','bad_decimal','zero_volume','wrong_range','extra_column','wrong_quote_code','wrong_quote_market','wrong_quote_name','quote_error','missing_quote','quote_not_next_session','quote_future','endpoint_mismatch','archive_price','archive_provider','too_few_archive','duplicate_archive','foreign_host','unadjusted','naive_clock','future_clock','premature_clock','changed_bytes','symlink','promoted_official'])
def test_unverified_or_misbound_bse_inputs_cannot_become_a_path(tmp_path,change):
    calendar,source,_=fixture(tmp_path,change)
    with pytest.raises(ValueError):bse.source_stock(tmp_path,source['content_digest'],calendar)


@pytest.mark.parametrize('change',['new_path','old_path','benchmark','source_class','parent','mixed','unknown'])
def test_redigesting_a_changed_packet_cannot_bypass_source_or_ancestry_checks(tmp_path,change):
    calendar,source,_=fixture(tmp_path);base=base_packet(tmp_path,calendar);packet=bse.extension_packet(base,source['content_digest'],root=tmp_path)
    if change=='new_path':packet['data']['stocks']['920023.BJ']['points'][5]['value']=99
    elif change=='old_path':packet['data']['stocks']['000001.SZ']['points'][5]['value']=99
    elif change=='benchmark':packet['data']['market'][5]['value']=99
    elif change=='source_class':packet[bse.EXTENSION_KEY]['checks']['official_daily_crosscheck']=True;seal(packet[bse.EXTENSION_KEY])
    elif change=='parent':packet[bse.EXTENSION_KEY]['base_price_digest']='a'*64;seal(packet[bse.EXTENSION_KEY])
    elif change=='mixed':packet['subject_extension']={'base_price_digest':base['content_digest']}
    else:packet['unknown_extension']={'base_price_digest':base['content_digest']}
    seal(packet)
    with pytest.raises((ValueError,FileNotFoundError)):validate_price_packet(packet,root=tmp_path)


def test_mixed_legacy_calendar_bse_and_later_subject_extension_revalidates_bse_ancestor(tmp_path):
    from test_research_history_prefix import build
    from research_history_subjects import extension_packet as add_legacy_subject
    _,legacy,_,_=build(tmp_path);atomic_write_json(tmp_path/'price_paths/history'/(legacy['content_digest']+'.json'),legacy)
    calendar,source,folder=fixture(tmp_path,calendar=legacy['data']['calendar'])
    current=bse.extension_packet(legacy,source['content_digest'],root=tmp_path);atomic_write_json(tmp_path/'price_paths/history'/(current['content_digest']+'.json'),current)
    data=deepcopy(current['data']);data['stocks']['000002.SZ']=deepcopy(data['stocks']['000001.SZ']);data['source_digests']['new']='b'*64
    outer=add_legacy_subject(current,data,root=tmp_path);validate_price_packet(outer,root=tmp_path)
    (folder/(source['prices']['sha256']+'.json')).write_text('{}')
    with pytest.raises(ValueError):validate_price_packet(outer,root=tmp_path)


def test_bse_identifier_routes_do_not_resolve_to_sse_or_szse(monkeypatch):
    from fastapi.testclient import TestClient
    import api,research_history
    monkeypatch.setattr(research_history,'load',lambda symbol=None:{'availability':'available','symbol':symbol})
    client=TestClient(api.app)
    assert client.get('/api/v1/workbench/history/920023.BJ').json()['data']['symbol']=='920023.BJ'
    assert client.get('/api/v1/workbench/history/920023.SH').status_code==422
    assert client.get('/api/v1/workbench/history/920023').status_code==422
    assert client.post('/api/v1/workbench/history/920023.BJ').status_code==405
    assert research_history.mentioned('田野920023',{'920023.BJ':'*ST田野','603272.SH':'*ST联翔'})==['920023.BJ']


def test_issuer_lifecycle_notice_is_not_labelled_as_a_price_provider():
    from research_history import assemble
    day='2026-05-11';points=[{'date':day,'value':2.,'level':100.,'basis':'historical_qfq'}]
    event='https://static.cninfo.com.cn/finalpage/2026-10-23/1225615607.PDF'
    paths={'calendar':[day],'stocks':{'000016.SZ':{'name':'康佳A（已摘牌）','points':points,'event_source_url':event}},'market':points,'st':points,'st_name':'ST参考','st_note':'原始参考','st_source_url':'https://example.test/st'}
    record={'id':'original','kind':'original_question','asked_at':'2026-05-11T07:00:00+00:00','question':'康佳？','answers':[],'symbols':['000016.SZ'],'sources':[]}
    detail=assemble([record],paths)['details']['000016.SZ']
    assert detail['source_urls']['stock_event']==event
    assert 'stock_history' not in detail['source_urls']
