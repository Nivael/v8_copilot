"""Small synthetic securities across the real declared calendar; no current-market fixture claims."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import hashlib
import json

import pytest

from canonical_json import digest
import sse_history_archive as m

NOW=datetime(2026,11,6,tzinfo=timezone.utc)
FETCH='2026-11-05T05:30:00+00:00'
WINDOW=m.recent_calendar_window('2026-11-04')


def write_ref(folder,payload,url,params,**extra):
    folder.mkdir(parents=True,exist_ok=True);data=json.dumps(payload,ensure_ascii=False).encode();sha=hashlib.sha256(data).hexdigest()
    (folder/(sha+'.raw')).write_bytes(data)
    return {'url':url,'params':params,'sha256':sha,'bytes':len(data),'observed_at':FETCH,**extra}


def envelope(rows,sql,page=1):
    return {'sqlId':sql,'isPagination':'true','actionErrors':[],'fieldErrors':{},'result':rows,
            'pageHelp':{'data':rows,'pageNo':page,'pageSize':500,'pageCount':1,'total':len(rows)}}


@pytest.fixture
def capture(tmp_path):
    capture=tmp_path/'capture';universe=capture/'universe';prices=capture/'full_prices';refs=[]
    registries={'1':[{'A_STOCK_CODE':'600001','LIST_DATE':'20200101','DELIST_DATE':'20261019','COMPANY_ABBR':'已退出样本','STOCK_TYPE':'1'},
                     {'A_STOCK_CODE':'600002','LIST_DATE':'20200101','DELIST_DATE':'-','COMPANY_ABBR':'原有样本','STOCK_TYPE':'1'}],
                '8':[{'A_STOCK_CODE':'688001','LIST_DATE':'20260917','DELIST_DATE':'-','COMPANY_ABBR':'新上市样本','STOCK_TYPE':'8'}]}
    for board,rows in registries.items():
        params={**m.REGISTRY_PARAMS,'STOCK_TYPE':board,'pageHelp.pageNo':1,'pageHelp.beginPage':1,'pageHelp.endPage':1}
        refs.append(write_ref(universe,envelope(rows,m.REGISTRY_PARAMS['sqlId']),m.REGISTRY_URL,params))
    for day in WINDOW['calendar']:
        counts={'01':2-int(day>='2026-10-19'),'02':0,'03':int(day>='2026-09-17')};counts['17']=counts['01']+counts['03']
        rows=[{'PRODUCT_CODE':k,'TRADE_DATE':day.replace('-',''),'LIST_NUM':str(v)} for k,v in counts.items()]
        # A missing repo category is not a missing ordinary-stock class or an inferred zero.
        payload=envelope(rows,m.OVERVIEW_PARAMS['sqlId']);payload['isPagination']='false';payload['pageHelp']['data']=None
        refs.append(write_ref(universe,payload,m.QUERY_URL,{**m.OVERVIEW_PARAMS,'SEARCH_DATE':day}))
    endpoint_dir=tmp_path/'endpoint';(endpoint_dir/'snapshots').mkdir(parents=True);(endpoint_dir/'responses').mkdir()
    source={'total':2,'time':150000,'date':20261104,'begin':0,'end':2,'list':[
        ['600002','原有样本',10,10,0,100,1000,'T','ASH',''],['688001','新上市样本',20,20,0,100,2000,'T','KSH','']]}
    data=json.dumps(source).encode();sha=hashlib.sha256(data).hexdigest();(endpoint_dir/'responses'/(sha+'.json')).write_bytes(data)
    endpoint={'contract_version':m.ENDPOINT_VERSION,'sources':m.SOURCES,'requested_through':'2026-11-04','fetched_at':FETCH,
              'venues':{'SSE':m.parse_sse([source],'2026-11-04')},'responses':[{'venue':'SSE','url':m.SOURCES['SSE']['api_url'],
              'params':{'select':m.SSE_SELECT,'begin':0,'end':500},'observed_at':FETCH,'response_sha256':sha,'bytes':len(data)}]}
    key=digest(endpoint);endpoint['content_digest']=key;(endpoint_dir/'snapshots'/(key+'.json')).write_text(json.dumps(endpoint))
    basis={'window':WINDOW,'source_refs':refs,'endpoint_snapshot':key,'rows':['injected summary is ignored']}
    (universe/'complete.json').write_text(json.dumps(basis));price_refs=[]
    for code,value in [('600001',30),('600002',10),('688001',20)]:
        days=[d for d in WINDOW['calendar'] if (code!='600001' or d<'2026-10-19') and (code!='688001' or d>='2026-09-17')]
        rows=[[int(d.replace('-','')),value,value,0,100,value*100] for d in days if not(code=='600001' and d=='2026-09-08')]
        if code=='600001':
            at=next(i for i,r in enumerate(rows) if r[0]==20260909);rows[at][4:]=[0,0]
        else:rows.append([20261105,0,value,-100,0,0])  # Unclosed placeholder stays excluded.
        price_refs.append(write_ref(prices,{'code':code,'total':len(rows),'begin':0,'end':len(rows),'kline':rows},m.PRICE_URL+code,m.PARAMS,
                                    code=code,status='captured'))
    plan={'version':'sse_full_price_capture_plan_v1','through':'2026-11-04','start':WINDOW['start'],'basis_digest':digest(basis),
          'codes':['600001','600002','688001'],'params':m.PARAMS}
    (prices/'plan.json').write_text(json.dumps(plan));(prices/'complete.json').write_text(json.dumps({'version':'sse_full_price_capture_v1',
        'plan_digest':digest(plan),'started_at':FETCH,'completed_at':FETCH,'status':'captured','source_refs':price_refs}))
    return capture,endpoint_dir


def rewrite_source(capture,group,modify,index=0):
    path=capture/group/'complete.json';raw=json.loads(path.read_text());ref=raw['source_refs'][index]
    payload=json.loads((capture/group/(ref['sha256']+'.raw')).read_text());modify(payload,ref)
    new=write_ref(capture/group,payload,ref['url'],ref['params'],**{k:v for k,v in ref.items() if k not in ('url','params','sha256','bytes','observed_at')})
    raw['source_refs'][index]=new;path.write_text(json.dumps(raw))
    if group=='universe':
        planpath=capture/'full_prices/plan.json';plan=json.loads(planpath.read_text());plan['basis_digest']=digest(raw);planpath.write_text(json.dumps(plan))
        fullpath=capture/'full_prices/complete.json';full=json.loads(fullpath.read_text());full['plan_digest']=digest(plan);fullpath.write_text(json.dumps(full))


def test_reconstructs_populations_without_a_survivor_filter_or_zero_filling(capture):
    folder,endpoint=capture;result=m.project(folder,endpoint,NOW)
    assert result['availability']=='observed' and result['distinct_securities']==3 and result['registry_source_rows']==3
    assert result['days'][0]['listed_members']==2 and result['days'][-1]['listed_members']==2
    assert next(d for d in result['days'] if d['date']=='2026-09-17')['listed_members']==3
    assert result['ended_listings'][0]['code']=='600001' and result['new_listings'][0]['code']=='688001'
    assert result['not_returned_days']==1 and result['explicit_nontrading_days']==1
    assert next(d for d in result['days'] if d['date']=='2026-09-08')['not_returned']==['600001.SH']
    assert next(d for d in result['days'] if d['date']=='2026-09-09')['explicit_nontrading']==['600001.SH']
    assert result['observed_trading_days']==result['expected_security_days']-2
    assert result['historical_breadth_ready'] is result['historical_ST_ready'] is result['historical_PIT'] is result['effect_measured'] is False
    assert result['endpoint_compared_trading']==2 and all(d['date']<='2026-11-04' for d in result['days'])


@pytest.mark.parametrize('damage',['filtered','date','board','listed','delisted','duplicate','missing_overview','count','page','error','missing_star'])
def test_registry_queries_dates_population_and_totals_are_bound(capture,damage):
    folder,endpoint=capture
    if damage=='missing_overview':
        p=folder/'universe/complete.json';x=json.loads(p.read_text());x['source_refs'].pop();p.write_text(json.dumps(x))
    elif damage=='missing_star':
        p=folder/'universe/complete.json';x=json.loads(p.read_text());x['source_refs'].pop(1);p.write_text(json.dumps(x))
    elif damage in ('date','board','count'):
        def change(x,r):
            if damage=='date':x['result'][0]['TRADE_DATE']='20260903'
            elif damage=='board':x['result'].pop(0)
            else:x['result'][0]['LIST_NUM']='9000'
        rewrite_source(folder,'universe',change,2)
    else:
        def change(x,r):
            if damage=='filtered':r['params']['STOCK_CODE']='600001'
            elif damage=='listed':x['result'][0]['LIST_DATE']='20260917'
            elif damage=='delisted':x['result'][0]['DELIST_DATE']='-'
            elif damage=='duplicate':x['result'][1]['A_STOCK_CODE']='600001'
            elif damage=='page':r['params']['pageHelp.pageNo']=2
            else:x['actionErrors']=['upstream failure']
        rewrite_source(folder,'universe',change)
    with pytest.raises((ValueError,KeyError)):m.project(folder,endpoint,NOW)


@pytest.mark.parametrize('damage',['code','query','bounds','duplicate_day','future_day','zero_reference','activity','percentage','pre_listing','endpoint'])
def test_quote_identity_activity_dates_and_independent_endpoint_are_verified(capture,damage):
    folder,endpoint=capture
    def change(x,r):
        if damage=='code':x['code']='600009'
        elif damage=='query':r['params']['select']='date,close,volume'
        elif damage=='bounds':x['end']-=1
        elif damage=='duplicate_day':x['kline'][1][0]=x['kline'][0][0]
        elif damage=='future_day':x['kline'][-1][0]=20261107
        elif damage=='zero_reference':x['kline'][0][2]=0
        elif damage=='activity':x['kline'][0][4]=0
        elif damage=='percentage':x['kline'][0][3]=10
        elif damage=='pre_listing':x['kline'][0][0]=20260904
        else:x['kline'][-2][4:]=[200,2000]
    rewrite_source(folder,'full_prices',change,2 if damage=='pre_listing' else 1)
    with pytest.raises(ValueError):m.project(folder,endpoint,NOW)


def test_dividend_reference_is_not_overwritten_by_the_previous_close(capture):
    folder,endpoint=capture
    def change(x,_):x['kline'][1][1:4]=[10,9.9,1.01]
    rewrite_source(folder,'full_prices',change,1)
    b=m.read_basis(folder,NOW);raw=json.loads((folder/'full_prices/complete.json').read_text());ref=raw['source_refs'][1]
    rows=m.parse_prices(m.body(folder/'full_prices',ref,NOW),ref,b,NOW)
    assert rows['2026-09-07']['prev_close']=='9.9' and rows['2026-09-04']['last']=='10'
    assert m.project(folder,endpoint,NOW)['availability']=='observed'


def test_an_ipo_has_no_fabricated_pre_listing_flat_days(capture):
    folder,endpoint=capture;report=m.project(folder,endpoint,NOW)
    assert '688001.SH' not in next(d for d in report['days'] if d['date']=='2026-09-16')['not_returned']
    assert next(d for d in report['days'] if d['date']=='2026-09-17')['observed_trading']==3


@pytest.mark.parametrize('group',['universe','full_prices','endpoint'])
def test_readers_recheck_original_bytes_and_preserve_published_snapshots(capture,tmp_path,group):
    folder,endpoint=capture;output=tmp_path/'published';m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW)
    before=(output/'current.json').read_bytes();key=json.loads(before)['input_digest'];stored=output/'sources'/key
    path=next((endpoint/'responses').glob('*.json')) if group=='endpoint' else next((stored/group).glob('*.raw'))
    path.write_bytes(b'changed source')
    assert m.archive_status(output,endpoint_dir=endpoint,now=NOW)['availability']=='invalid'
    assert (output/'current.json').read_bytes()==before


def test_injected_summary_cannot_turn_an_archive_into_historical_market_coverage(capture,tmp_path):
    folder,endpoint=capture;output=tmp_path/'published';m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW)
    p=output/'current.json';r=json.loads(p.read_text());r['report']={'historical_breadth_ready':True,'historical_ST_ready':True,'return_pct':999}
    r['content_digest']=digest({k:v for k,v in r.items() if k!='content_digest'});p.write_text(json.dumps(r))
    actual=m.archive_status(output,endpoint_dir=endpoint,now=NOW)
    assert actual['historical_breadth_ready'] is actual['historical_ST_ready'] is False and 'return_pct' not in actual


def test_failed_ingest_or_foreign_output_cannot_replace_current(capture,tmp_path):
    folder,endpoint=capture;output=tmp_path/'published';m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW);before=(output/'current.json').read_bytes()
    source=next((folder/'full_prices').glob('*.raw'));source.write_bytes(b'failed source')
    with pytest.raises(ValueError):m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW)
    assert (output/'current.json').read_bytes()==before
    assert m.archive_status(output,endpoint_dir=endpoint,now=NOW)['availability']=='observed'
    (output/'current.json').write_text('{"version":"foreign"}')
    with pytest.raises(ValueError,match='foreign'):m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW)


def test_a_copy_failure_does_not_corrupt_previously_published_originals(capture,tmp_path,monkeypatch):
    folder,endpoint=capture;output=tmp_path/'published';m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW);before=(output/'current.json').read_bytes()
    real=m.project;called=0
    def mutate_after_read(*args):
        nonlocal called
        result=real(*args);called+=1
        if called==1:next((folder/'full_prices').glob('*.raw')).write_bytes(b'changed after validation')
        return result
    monkeypatch.setattr(m,'project',mutate_after_read)
    with pytest.raises(ValueError):m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW)
    monkeypatch.setattr(m,'project',real)
    assert (output/'current.json').read_bytes()==before and m.archive_status(output,endpoint_dir=endpoint,now=NOW)['availability']=='observed'


@pytest.mark.parametrize('damage',['missing_security','duplicate_security','future_capture','unfinished','plan','processor'])
def test_capture_completeness_and_loaded_code_are_required(capture,tmp_path,monkeypatch,damage):
    folder,endpoint=capture;p=folder/'full_prices/complete.json';raw=json.loads(p.read_text())
    if damage=='missing_security':raw['source_refs'].pop()
    elif damage=='duplicate_security':raw['source_refs'].append(deepcopy(raw['source_refs'][0]))
    elif damage=='future_capture':raw['completed_at']=(NOW+timedelta(days=1)).isoformat()
    elif damage=='unfinished':raw['status']='collecting'
    elif damage=='plan':raw['plan_digest']='different'
    else:monkeypatch.setattr(m,'processor_digest',lambda:'different')
    p.write_text(json.dumps(raw))
    with pytest.raises(ValueError):m.materialize(folder,output=tmp_path/'published',endpoint_dir=endpoint,now=NOW)


class CapturedClient:
    def __init__(self,source,fail=None):
        self.source=source;self.fail=fail;self.calls=[];self.refs={}
        for group in ('universe','full_prices'):
            raw=json.loads((source/group/'complete.json').read_text())
            for ref in raw['source_refs']:self.refs[digest({'url':ref['url'],'params':ref['params']})]=(group,ref)
    def request(self,folder,url,params,*,code=None,validate=None):
        self.calls.append((url,params))
        if self.fail is not None and code==self.fail:raise TimeoutError('synthetic upstream failure')
        group,ref=self.refs[digest({'url':url,'params':params})];folder.mkdir(parents=True,exist_ok=True)
        (folder/(ref['sha256']+'.raw')).write_bytes((self.source/group/(ref['sha256']+'.raw')).read_bytes())
        payload=m.body(folder,ref,NOW)
        if validate:validate(payload,ref)
        return payload,deepcopy(ref)


def test_explicit_collection_validates_and_publishes_without_advancing_fetch_times(capture,tmp_path):
    from sse_history_collect import collect
    folder,endpoint=capture;original=json.loads(next((endpoint/'snapshots').glob('*.json')).read_text())
    (endpoint/'current.json').write_text(json.dumps(original));client=CapturedClient(folder);updates=[]
    result=collect(client,through='2026-11-04',capture=tmp_path/'new-capture',endpoint_dir=endpoint,output=tmp_path/'published',now=NOW,progress=updates.append)
    assert result['distinct_securities']==3 and len(client.calls)==43
    assert updates[-1]['status']=='complete' and updates[-1]['completed_price_sources']==3
    status=m.archive_status(tmp_path/'published',endpoint_dir=endpoint,now=NOW)
    assert status['source_fetched_at']==FETCH and status['materialized_at']==NOW.isoformat()


def test_failed_collection_keeps_the_last_complete_archive(capture,tmp_path):
    from sse_history_collect import collect
    folder,endpoint=capture;output=tmp_path/'published';m.materialize(folder,output=output,endpoint_dir=endpoint,now=NOW);before=(output/'current.json').read_bytes()
    (endpoint/'current.json').write_bytes(next((endpoint/'snapshots').glob('*.json')).read_bytes())
    with pytest.raises(TimeoutError):collect(CapturedClient(folder,fail='600002'),through='2026-11-04',capture=tmp_path/'failed',endpoint_dir=endpoint,output=output,now=NOW)
    report=json.loads((tmp_path/'failed/collection.json').read_text())
    assert report['status']=='failed' and report['error_type']=='TimeoutError' and (output/'current.json').read_bytes()==before
    assert m.archive_status(output,endpoint_dir=endpoint,now=NOW)['availability']=='observed'


def test_foreign_collection_directory_is_rejected_before_network_work(capture,tmp_path):
    from sse_history_collect import collect
    folder,endpoint=capture;(endpoint/'current.json').write_bytes(next((endpoint/'snapshots').glob('*.json')).read_bytes())
    foreign=tmp_path/'foreign';foreign.mkdir();(foreign/'collection.json').write_text('{"version":"other-source"}');client=CapturedClient(folder)
    with pytest.raises(ValueError,match='foreign'):collect(client,through='2026-11-04',capture=foreign,endpoint_dir=endpoint,now=NOW)
    assert client.calls==[] and (foreign/'collection.json').read_text()=='{"version":"other-source"}'


def test_network_cache_reuses_only_hash_verified_originals(tmp_path,monkeypatch):
    import sse_history_collect as c
    url=m.PRICE_URL+'600001';full=url+'?'+c.urlencode(m.PARAMS);responses=[b'{"source":"one"}',b'{"source":"two"}'];calls=[]
    class Response:
        def __init__(self,data):self.data=data;self.url=full;self.headers={}
        def __enter__(self):return self
        def __exit__(self,*_):return None
        def read(self,_):return self.data
    def fetch(request,**_):calls.append(request.full_url);return Response(responses.pop(0))
    monkeypatch.setattr(c,'urlopen',fetch);monkeypatch.setattr(c.time,'sleep',lambda _:None)
    _,first=c.SourceClient().request(tmp_path,url,m.PARAMS,code='600001')
    _,same=c.SourceClient(repair=True).request(tmp_path,url,m.PARAMS,code='600001')
    assert first==same and calls==[full]
    (tmp_path/(first['sha256']+'.raw')).write_bytes(b'changed cached bytes')
    _,fixed=c.SourceClient(repair=True).request(tmp_path,url,m.PARAMS,code='600001')
    assert fixed['sha256']!=first['sha256'] and len(calls)==2


def test_observation_ranges_compare_instants_across_timezones(capture):
    folder,endpoint=capture;p=folder/'full_prices/complete.json';raw=json.loads(p.read_text())
    raw['source_refs'][0]['observed_at']='2026-11-05T06:00:00+00:00'
    raw['source_refs'][1]['observed_at']='2026-11-05T13:45:00+08:00'
    raw['completed_at']='2026-11-05T06:01:00+00:00';p.write_text(json.dumps(raw))
    result=m.project(folder,endpoint,NOW)
    assert result['source_fetched_at']=='2026-11-05T06:00:00+00:00' and result['first_price_observed_at']==FETCH


def test_verified_price_archive_does_not_promote_complete_market_or_ST_coverage(tmp_path,monkeypatch):
    from market_risk import build_market_risk_status,market_update_status
    fake={'version':m.VERSION,'availability':'observed','start':'2026-09-04','through':'2026-11-04','distinct_securities':3,
          'price_responses':3,'observed_trading_days':80,'source_fetched_at':FETCH,'historical_breadth_ready':False,'historical_ST_ready':False,'effect_measured':False}
    monkeypatch.setattr('market_risk.sse_history_archive_status',lambda *args,**kwargs:deepcopy(fake))
    status=build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'missing.db',manifest_path=tmp_path/'missing.json',now=NOW)
    assert status['market_coverage']['historical_breadth_venues_at_target']==0 and status['market_coverage']['st_style_at_target'] is False
    assert status['node_market_comparison']['status']=='not_evaluated' and status['parameters']['risk_weights'] is None
    row=next(r for r in market_update_status(snapshot_dir=tmp_path,now=NOW) if r['source_id']=='sse_historical_price_archive')
    assert row['coverage_basis']=='price_archives' and row['observed_source_groups']==row['declared_series']==3
    assert row['series_at_target'] is None and row['observation_count']==80 and row['observation_unit']=='有成交股票日'


@pytest.mark.parametrize('kind',['registry','daily_total','endpoint_parent','endpoint_source'])
def test_source_observation_chronology_cannot_predate_its_represented_market_dates(capture,kind):
    folder,endpoint=capture
    if kind in ('registry','daily_total'):
        path=folder/'universe/complete.json';raw=json.loads(path.read_text());index=0 if kind=='registry' else 2
        raw['source_refs'][index]['observed_at']='2026-09-03T01:00:00+00:00';path.write_text(json.dumps(raw))
        with pytest.raises(ValueError,match='observation predates'):m.read_basis(folder,NOW)
    else:
        raw=json.loads(next((endpoint/'snapshots').glob('*.json')).read_text());raw.pop('content_digest')
        if kind=='endpoint_parent':raw['fetched_at']='2026-11-03T01:00:00+00:00'
        else:raw['responses'][0]['observed_at']='2026-11-03T01:00:00+00:00'
        key=digest(raw);raw['content_digest']=key;(endpoint/'snapshots'/(key+'.json')).write_text(json.dumps(raw))
        with pytest.raises(ValueError,match='observation'):m.read_endpoint(endpoint,key,'2026-11-04',NOW)


@pytest.mark.parametrize('observed',['2026-11-05T04:00:00+00:00','2026-11-05T06:00:00+00:00'])
def test_endpoint_start_time_is_separate_from_reused_or_new_page_observations(capture,observed):
    _,endpoint=capture;raw=json.loads(next((endpoint/'snapshots').glob('*.json')).read_text());raw.pop('content_digest')
    raw['responses'][0]['observed_at']=observed;key=digest(raw);raw['content_digest']=key
    (endpoint/'snapshots'/(key+'.json')).write_text(json.dumps(raw))
    assert len(m.read_endpoint(endpoint,key,'2026-11-04',NOW))==2
