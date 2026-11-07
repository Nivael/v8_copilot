from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from canonical_json import digest
import exchange_risk_membership as m

NOW=datetime(2026,11,5,4,tzinfo=timezone.utc)


def sse(rows,group):
    n=len(rows)
    return {'result':rows,'pageHelp':{'total':n,'data':rows,'pageNo':1,'pageCount':int(bool(n)),'pageSize':n,'pageSizeWithOutLimit':n},
            'sqlId':m.GROUPS[group]['params']['sqlId'],'actionErrors':[],'actionMessages':[],'fieldErrors':{},'isPagination':'false',
            'queryDate':'','type':m.GROUPS[group]['params'].get('type','')}


def szrow(code,name):
    return {'zqdm':code,'gsjc':f"<a href='http://www.szse.cn/certificate/individual/index.html?code={code}' target='_blank'><u>{name}</u></a>"}


def table(tab,rows,page,total):
    return {'metadata':{'tabkey':tab,'catalogid':'fxjsb','name':'风险警示股票' if tab=='tab1' else '退市整理股票',
            'recordcount':total,'pagesize':2,'pagecount':(total+1)//2,'pageno':page,'cols':{'zqdm':'证券代码','gsjc':'证券简称'},
            'conditions':[],'subname':'2026-11-05 '},'data':rows}


@pytest.fixture
def archive(tmp_path,monkeypatch):
    proof={'sse_definition':'var riskplate = { synthetic:true };\nvar kcbriskplate = { synthetic:true };\n//科创板风险警示end',
           'szse_definition':'<div class="report-container" data-s-catalog-id="fxjsb" data-s-data-url=""></div>'}
    monkeypatch.setattr(m,'PROOFS',{key:(m.PROOFS[key][0],hashlib.sha256(value.encode()).hexdigest()) for key,value in proof.items()})
    payload={**proof,
        'sse_main_risk':sse([{'INSTRUMENT_ID':'600001','INSTRUMENT_SHORT':'ST示例'},{'INSTRUMENT_ID':'900001','INSTRUMENT_SHORT':'ST示例B'}],'sse_main_risk'),
        'sse_main_delisting':sse([{'INSTRUMENT_ID':'600002','INSTRUMENT_SHORT':'示例退'}],'sse_main_delisting'),
        'sse_star_risk':sse([{'secCode':'688001','secNameCn':'ST科创'}],'sse_star_risk'),
        'sse_star_delisting':sse([],'sse_star_delisting'),
        'szse_risk:1':[table('tab1',[szrow('000001','ST深一'),szrow('300001','ST创业')],1,4),table('tab2',[],1,0)],
        'szse_risk:2':[table('tab1',[szrow('000002','ST深二'),szrow('200001','ST深B')],2,4),table('tab2',[],1,0)],
        'szse_delisting:1':[table('tab1',[],1,0),table('tab2',[szrow('002731','示例退')],1,1)]}
    class Fake:
        def __init__(self):self.responses=[]
        def fetch(self,key,url,params):
            item=payload[key];text=item if isinstance(item,str) else json.dumps(item,ensure_ascii=False)
            raw=text.encode();sha=hashlib.sha256(raw).hexdigest();directory=tmp_path/'responses';directory.mkdir(exist_ok=True)
            (directory/(sha+'.raw')).write_bytes(raw)
            self.responses.append({'key':key,'url':url,'params':params,'final_url':url+('?' + m.urlencode(params) if params else ''),
                                   'observed_at':NOW.isoformat(),'response_sha256':sha,'bytes':len(raw)})
            return text
    return tmp_path,payload,Fake


def publish(archive):
    directory,payload,Fake=archive;m.collect(output=directory,collector=Fake(),now=NOW)
    return json.loads((directory/'current.json').read_text())


def test_selected_tabs_full_pages_share_classes_and_source_dates_remain_distinct(archive):
    raw=publish(archive);data=m.list_status(archive[0],now=NOW)
    assert data['availability']=='observed'
    assert (data['risk_warning_a_shares'],data['delisting_a_shares'],data['excluded_b_shares'])==(5,2,2)
    assert len(data['groups'])==6 and len(data['rows'])==9 and len(raw['responses'])==9
    assert data['common_source_as_of'] is None and data['historical_membership_ready'] is data['historical_first_observation'] is False
    assert all(row['source_as_of'] is None for row in data['groups'] if row['venue']=='SSE')
    assert all(row['source_as_of']=='2026-11-05' for row in data['groups'] if row['venue']=='SZSE')
    assert next(row for row in data['groups'] if row['group']=='szse_delisting')['a_shares']==1
    assert next(row for row in data['groups'] if row['group']=='sse_star_delisting')['a_shares']==0


def test_unselected_zero_counter_is_not_the_selected_delisting_list(archive):
    raw=publish(archive)
    assert archive[1]['szse_risk:1'][1]['metadata']['recordcount']==0
    data=m.project(raw,archive[0],NOW)
    assert {row['ts_code'] for row in data['rows'] if row['kind']=='delisting'}=={'600002.SH','002731.SZ'}


@pytest.mark.parametrize('bad',['catalog','tab','name','date','columns','conditions','total','size','pagecount','pageno','rows'])
def test_wrong_selected_tab_metadata_or_incomplete_page_cannot_publish(archive,bad):
    row=archive[1]['szse_risk:2'][0];meta=row['metadata']
    if bad=='catalog':meta['catalogid']='different'
    elif bad=='tab':meta['tabkey']='tab2'
    elif bad=='name':meta['name']='退市整理股票'
    elif bad=='date':meta['subname']='2026-11-04'
    elif bad=='columns':meta['cols']['zqdm']='股票名称'
    elif bad=='conditions':meta['conditions']=['txtQueryDate']
    elif bad=='total':meta['recordcount']=3
    elif bad=='size':meta['pagesize']=True
    elif bad=='pagecount':meta['pagecount']=3
    elif bad=='pageno':meta['pageno']=1
    else:row['data'].pop()
    with pytest.raises((ValueError,KeyError)):publish(archive)
    assert not (archive[0]/'current.json').exists()


@pytest.mark.parametrize('bad',['sql','errors','pagination','future_query','total_bool','total_float','row_mismatch','pagecount','page_size','star_type'])
def test_sse_response_must_match_the_complete_reviewed_query(archive,bad):
    row=archive[1]['sse_star_risk']
    if bad=='sql':row['sqlId']='another'
    elif bad=='errors':row['actionErrors']=['unavailable']
    elif bad=='pagination':row['isPagination']='true'
    elif bad=='future_query':row['queryDate']='2026-11-06'
    elif bad=='total_bool':row['pageHelp']['total']=True
    elif bad=='total_float':row['pageHelp']['total']=1.0
    elif bad=='row_mismatch':row['pageHelp']['data']=[]
    elif bad=='pagecount':row['pageHelp']['pageCount']=2
    elif bad=='page_size':row['pageHelp']['pageSize']=20
    else:row['type']='1'
    with pytest.raises(ValueError):publish(archive)


@pytest.mark.parametrize('bad',['duplicate_page_security','risk_delisting_overlap','changed_name_link','script_name','wrong_market_code','blank_name'])
def test_security_identity_scope_and_uniqueness_are_not_inferred_from_a_name(archive,bad):
    payload=archive[1]
    if bad=='duplicate_page_security':payload['szse_risk:2'][0]['data'][0]=deepcopy(payload['szse_risk:1'][0]['data'][0])
    elif bad=='risk_delisting_overlap':payload['sse_main_delisting']['result'][0]['INSTRUMENT_ID']='600001'
    elif bad=='changed_name_link':payload['szse_risk:1'][0]['data'][0]['gsjc']=szrow('999999','ST深一')['gsjc']
    elif bad=='script_name':payload['szse_risk:1'][0]['data'][0]['gsjc']='<script>bad()</script>'
    elif bad=='wrong_market_code':payload['sse_main_risk']['result'][0]['INSTRUMENT_ID']='000001'
    else:payload['sse_main_risk']['result'][0]['INSTRUMENT_SHORT']=' '
    with pytest.raises(ValueError):publish(archive)


@pytest.mark.parametrize('bad',['missing_page','duplicate_ref','extra_ref','time_naive','time_future','url','params','redirect','raw_bytes'])
def test_reader_rechecks_archived_requests_times_bytes_and_exact_page_set(archive,bad):
    raw=publish(archive);directory=archive[0];ref=raw['responses'][-1]
    if bad=='missing_page':raw['responses'].pop()
    elif bad=='duplicate_ref':raw['responses'].append(deepcopy(ref))
    elif bad=='extra_ref':raw['responses'].append({**ref,'key':'undeclared'})
    elif bad=='time_naive':ref['observed_at']='2026-11-05T04:00:00'
    elif bad=='time_future':ref['observed_at']='2026-11-06T04:00:00+00:00'
    elif bad=='url':ref['url']='https://example.com'
    elif bad=='params':ref['params']={**ref['params'],'txtQueryDate':'2026-11-04'}
    elif bad=='redirect':ref['final_url']=ref['final_url'].replace('www.szse.cn','example.com')
    else:(directory/'responses'/(ref['response_sha256']+'.raw')).write_bytes(b'changed')
    with pytest.raises((ValueError,KeyError)):m.project(raw,directory,NOW)


@pytest.mark.parametrize('proof',['sse_definition','szse_definition'])
def test_changed_source_definition_requires_review(archive,proof):
    archive[1][proof]+=' changed' if proof=='sse_definition' else ' duplicate '+archive[1][proof]
    if proof=='sse_definition':archive[1][proof]=archive[1][proof].replace('synthetic:true','synthetic:false')
    with pytest.raises(ValueError):publish(archive)


def test_duplicated_source_functions_do_not_reuse_the_first_valid_fragment(archive):
    archive[1]['sse_definition']+='\nvar riskplate = { different:true };'
    with pytest.raises(ValueError,match='ambiguous'):publish(archive)


def test_old_observation_is_not_promoted_to_a_new_or_historical_data_day(archive):
    publish(archive);data=m.list_status(archive[0],now=NOW+timedelta(days=1))
    assert data['availability']=='observed' and data['is_today_observation'] is False
    assert data['observed_on']=='2026-11-05' and data['common_source_as_of'] is None
    assert data['historical_membership_ready'] is False


def test_reads_do_not_collect_or_trust_an_injected_report(archive,monkeypatch):
    raw=publish(archive);raw['report']={'risk_warning_a_shares':999,'historical_membership_ready':True}
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});path=archive[0]/'current.json';path.write_text(json.dumps(raw))
    monkeypatch.setattr(m.Collector,'fetch',lambda *_:pytest.fail('reader invoked network'))
    before=path.read_bytes();data=m.list_status(archive[0],now=NOW)
    assert data['risk_warning_a_shares']==5 and data['historical_membership_ready'] is False and path.read_bytes()==before


def test_collection_failure_keeps_the_prior_complete_snapshot(archive):
    publish(archive);path=archive[0]/'current.json';before=path.read_bytes()
    class Failed(archive[2]):
        def fetch(self,key,url,params):
            if key=='szse_delisting:1':raise OSError('source down')
            return super().fetch(key,url,params)
    with pytest.raises(OSError):m.collect(output=archive[0],collector=Failed(),now=NOW)
    assert path.read_bytes()==before


def test_replay_rechecks_sources_preserves_acquisition_dates_and_does_not_fetch(archive,monkeypatch):
    original=publish(archive);path=archive[0]/'current.json';raw=deepcopy(original);raw['processor_digest']='0'*64
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});path.write_text(json.dumps(raw))
    monkeypatch.setattr(m.Collector,'fetch',lambda *_:pytest.fail('replay invoked network'))
    m.reparse(output=archive[0],now=NOW+timedelta(days=1));new=json.loads(path.read_text())
    assert new['observed_on']==original['observed_on'] and new['started_at']==original['started_at'] and new['completed_at']==original['completed_at']
    assert new['reparsed_at']==(NOW+timedelta(days=1)).isoformat() and new['processor_digest']==m.PROCESSOR
    assert m.list_status(archive[0],now=NOW+timedelta(days=1))['is_today_observation'] is False


def test_corrupt_replay_and_foreign_output_are_not_overwritten(archive):
    raw=publish(archive);path=archive[0]/'current.json';before=path.read_bytes()
    (archive[0]/'responses'/(raw['responses'][0]['response_sha256']+'.raw')).write_bytes(b'changed')
    with pytest.raises(ValueError):m.reparse(output=archive[0],now=NOW)
    assert path.read_bytes()==before
    path.write_text('{"version":"foreign"}');before=path.read_bytes()
    with pytest.raises(ValueError):m.collect(output=archive[0],collector=archive[2](),now=NOW)
    assert path.read_bytes()==before


def test_missing_or_corrupt_snapshots_do_not_report_zero_members(tmp_path):
    data=m.list_status(tmp_path,now=NOW)
    assert data['availability']=='missing' and 'risk_warning_a_shares' not in data
    (tmp_path/'current.json').write_text('broken');data=m.list_status(tmp_path,now=NOW)
    assert data['availability']=='invalid' and 'risk_warning_a_shares' not in data


def test_observed_lists_do_not_advance_market_prices_historical_membership_or_risk_gates(archive,monkeypatch):
    import market_risk
    publish(archive);directory=archive[0]
    monkeypatch.setattr(market_risk,'risk_membership_status',lambda *_,now:m.list_status(directory,now=now))
    data=market_risk.build_market_risk_status(snapshot_dir=directory,database=directory/'no-prices.db',manifest_path=directory/'no-manifest.json',now=NOW)
    assert data['exchange_risk_membership']['risk_warning_a_shares']==5
    assert data['requested_through'] is None and data['indices']==[]
    assert data['exchange_risk_membership']['historical_membership_ready'] is False
    assert data['node_market_comparison']['status']=='not_evaluated' and data['current_risk_assessment']=='not_calibrated'
    assert all(row['estimated_net_subscription_yuan'] is None for row in data['etf_aggregate'].values())


def test_learning_freshness_uses_observation_not_a_fabricated_common_source_date(archive,monkeypatch):
    import market_risk
    publish(archive);directory=archive[0]
    monkeypatch.setattr(market_risk,'risk_membership_status',lambda *_,now:m.list_status(directory,now=now))
    rows=market_risk.market_update_status(snapshot_dir=directory,now=NOW)
    row=next(row for row in rows if row['source_id']=='exchange_risk_membership')
    assert row['observation_date']=='2026-11-05' and row['date_basis']=='current_list_observation'
    assert row['observation_count']==9 and row['observed_source_groups']==6
    assert row['requested_through'] is row['observed_through_min'] is row['observed_through_max'] is row['series_at_target'] is None
