from copy import deepcopy
from hashlib import sha256
import json

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from research_history import assemble,deduplicate,import_pages,instant,load,mentioned,outcome,processor_digest,publish
from research_history_prices import bound,stock_path,vendor_st_path


def sample():
    calendar=['2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05','2026-06-08','2026-06-09']
    points=[{'date':day,'value':value,'level':value} for day,value in zip(calendar,[100,90,80,70,60,50,40],strict=True)]
    paths={'calendar':calendar,'stocks':{'002514.SZ':{'name':'*ST宝馨','points':points}},'market':points,'st':points,'st_name':'ST板块（东财）','st_note':'独立供应商序列，不拼接','st_source_url':'https://quote.eastmoney.com/bk/90.BK0511.html'}
    record={'id':'question','asked_at':'2026-06-02T08:50:00Z','question':'尾盘什么意思','symbols':['002514.SZ'],'kind':'original_question','answers':[{'text':'更像洗盘'}],'sources':[]}
    return paths,record


def test_exact_trading_sessions_do_not_count_calendar_days_or_missing_as_zero():
    paths,r=sample();points=paths['stocks']['002514.SZ']['points'];result=outcome(points,'2026-06-02',paths['calendar'])
    assert result['five_day']['date']=='2026-06-09'
    assert result['five_day']['change_pct']==pytest.approx((40/90-1)*100)
    assert result['twenty_day']=={'date':None,'change_pct':None}
    points[-1]['level']=None
    assert outcome(points,'2026-06-02',paths['calendar'])['latest']['change_pct'] is None
    assert outcome(points,'2026-06-09',paths['calendar'])['latest']['change_pct'] is None


@pytest.mark.parametrize('stamp,anchor',[('2026-06-02T06:38:00Z','2026-06-01'),('2026-06-02T08:50:00Z','2026-06-02'),('2026-06-02T17:00:00Z','2026-06-02'),('2026-06-06T08:00:00Z','2026-06-05')])
def test_anchor_uses_shanghai_last_completed_close_not_future_intraday_close(stamp,anchor):
    paths,r=sample();r['asked_at']=stamp
    row=assemble([r],paths)['details']['002514.SZ']['questions'][0]
    assert row['anchor_date']==anchor
    assert row['asked_on']==instant(stamp).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Shanghai')).date().isoformat()


def test_reviews_require_unchanged_question_answer_and_nonempty_exact_quote():
    paths,r=sample();key=digest({'asked_at':r['asked_at'],'question':r['question'],'answers':r['answers']})
    review={'question_digest':key,'price_digest':digest(paths),'then_quote':'更像洗盘','headline':'应纠正'}
    assert assemble([r],paths,reviews={'question':review})['details']['002514.SZ']['questions'][0]['review']==review
    changed=deepcopy(paths);changed['st'][-1]['level']=39
    assert assemble([r],changed,reviews={'question':review})['details']['002514.SZ']['questions'][0]['review'] is None
    r['answers'][0]['text']='新回答'
    assert assemble([r],paths,reviews={'question':review})['details']['002514.SZ']['questions'][0]['review'] is None
    r['answers'][0]['text']='更像洗盘'
    for quote in ['证实主力出货','']:
        with pytest.raises(ValueError,match='quote'):assemble([r],paths,reviews={'question':{**review,'then_quote':quote}})


def test_branch_copies_merge_without_merging_different_questions_or_saved_research():
    _,r=sample();copy=deepcopy(r);copy['sources']=[{'kind':'branch'}]
    other=deepcopy(r);other['id']='other';other['question']='是否买入'
    saved=deepcopy(r);saved['id']='saved';saved['kind']='saved_research'
    rows=deduplicate([r,copy,other,saved])
    assert len(rows)==3 and rows[0]['retry_or_branch_count']==2
    assert any(row['kind']=='saved_research' for row in rows)


def test_real_page_import_preserves_original_date_question_missing_answer_and_branch(tmp_path):
    page={'thread':{'id':'a','title':'宝馨'},'page':{'hasMore':False},'turns':[{'id':'t','startedAt':1780382314,'completedAt':None,'items':[{'id':'q','type':'userMessage','content':[{'type':'text','text':'尾盘偷袭什么意思'}]}]}]}
    (tmp_path/'chatgpt-a.json').write_text(json.dumps(page));page['thread']['id']='branch';(tmp_path/'chatgpt-b.json').write_text(json.dumps(page))
    records,sources=import_pages(tmp_path,{'002514.SZ'})
    assert len(records)==1 and records[0]['question']=='尾盘偷袭什么意思'
    assert records[0]['symbols']==['002514.SZ'] and not records[0]['answers']
    assert len(records[0]['sources'])==2 and 'earlier UI messages may exist' in sources[0]['capture_scope']
    assert mentioned('conversation 6a4e827b-f168-83ec-a4fd-6b7c8a098ad1',{'002514.SZ'})==[]


def test_unknown_gap_breaks_price_chain_and_suspension_remains_visible():
    days=['2026-09-03','2026-09-04','2026-09-07','2026-09-08']
    old={days[0]:{'close':10,'volume':100}}
    official={days[1]:{'close':9,'previous_close':10,'is_trading':True},days[2]:{'close':None,'previous_close':None,'is_trading':False},days[3]:{'close':9.9,'previous_close':9,'is_trading':True}}
    points=stock_path(days,old,official)
    assert points[-1]['level']==pytest.approx(99) and points[2]['level'] is None
    del official[days[2]]
    assert stock_path(days,old,official)[-1]['level'] is None
    old[days[2]]={'close':None,'volume':0}
    assert stock_path(days,old,official)[-1]['level'] is None


def vendor_fixture(root):
    folder=root/'inputs/vendor_st';folder.mkdir(parents=True)
    payload={'rc':0,'data':{'code':'BK0511','name':'ST股','klines':['2026-06-01,100,100,101,99,10,1000,2,0,0,1','2026-06-02,100,90,101,89,10,1000,12,-10,-10,1']}}
    raw=json.dumps(payload).encode();key=sha256(raw).hexdigest();(folder/(key+'.json')).write_bytes(raw)
    url='https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=90.BK0511&klt=101&fqt=0&beg=20260501&end=20260602&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'
    ref={'url':url,'response_url':url,'sha256':key,'bytes':len(raw),'observed_at':'2026-06-03T00:00:00+00:00'};atomic_write_json(folder/'current.json',ref)
    return folder,ref,payload


def test_vendor_st_identity_raw_bytes_calendar_and_reported_return_are_bound(tmp_path):
    folder,ref,payload=vendor_fixture(tmp_path);calendar=['2026-06-01','2026-06-02']
    points,_=vendor_st_path(tmp_path,calendar);assert points[-1]['level']==90
    with pytest.raises(ValueError):vendor_st_path(tmp_path,['2026-06-02'])
    (folder/(ref['sha256']+'.json')).write_bytes(b'{}')
    with pytest.raises(ValueError,match='source changed'):vendor_st_path(tmp_path,calendar)


@pytest.mark.parametrize('mutation',['identity','return','duplicate_day','nonfinite','url'])
def test_rehashed_vendor_response_cannot_change_index_or_price_semantics(tmp_path,mutation):
    folder,ref,payload=vendor_fixture(tmp_path)
    if mutation=='identity':payload['data']['code']='BK0000'
    elif mutation=='return':payload['data']['klines'][1]='2026-06-02,100,90,101,89,10,1000,12,10,-10,1'
    elif mutation=='duplicate_day':payload['data']['klines'][1]=payload['data']['klines'][0]
    elif mutation=='nonfinite':payload['data']['klines'][1]='2026-06-02,100,NaN,101,89,10,1000,12,-10,-10,1'
    else:ref['url']=ref['url'].replace('90.BK0511','90.BK0000');ref['response_url']=ref['url']
    raw=json.dumps(payload).encode();ref.update(sha256=sha256(raw).hexdigest(),bytes=len(raw));(folder/(ref['sha256']+'.json')).write_bytes(raw);atomic_write_json(folder/'current.json',ref)
    with pytest.raises(ValueError):vendor_st_path(tmp_path,['2026-06-01','2026-06-02'])


def test_publication_is_private_source_bound_and_never_writes_research_ledger(tmp_path):
    paths,r=sample();directory=tmp_path/'price_paths';directory.mkdir()
    import research_history_prices
    from pathlib import Path
    source={'data':paths,'processor_digest':sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest()};source['content_digest']=digest(source);atomic_write_json(directory/'current.json',source)
    imported={'records':[r],'sources':[{'kind':'original_archive','sha256':'source'}]}
    value=publish(imported,root=tmp_path)
    assert load(root=tmp_path)['coverage']['original_questions']==1
    assert load('002514.SZ',root=tmp_path)['questions'][0]['question']=='尾盘什么意思'
    assert not list(tmp_path.glob('*.sqlite*'))
    value['processor_digest']='old';value['content_digest']=digest({k:v for k,v in value.items() if k!='content_digest'});atomic_write_json(tmp_path/'current.json',value)
    assert load(root=tmp_path)=={'availability':'updating'}
    value['data']='changed';atomic_write_json(tmp_path/'current.json',value)
    with pytest.raises(ValueError):bound(tmp_path/'current.json')
    source['processor_digest']='old';source['content_digest']=digest({k:v for k,v in source.items() if k!='content_digest'});atomic_write_json(directory/'current.json',source)
    with pytest.raises(ValueError,match='processor changed'):publish(imported,root=tmp_path)


def test_market_questions_remain_accessible_without_inventing_stock_identity():
    paths,r=sample();r['symbols']=[]
    result=assemble([r],paths)
    assert result['details']['market']['questions'][0]['question']=='尾盘什么意思'
    assert 'stock' not in result['details']['market']['chart_sources']


def test_history_api_routes_are_read_only_and_reject_invalid_symbol(monkeypatch):
    from fastapi.testclient import TestClient
    import research_history
    from api import app
    monkeypatch.setattr(research_history,'load',lambda symbol=None:{'availability':'available','as_of':'2026-06-02','stocks':[]} if symbol is None else {'availability':'available','symbol':symbol,'questions':[]})
    client=TestClient(app)
    assert client.get('/api/v1/workbench/history').json()['data']['stocks']==[]
    assert client.get('/api/v1/workbench/history/002514.SZ').json()['data']['symbol']=='002514.SZ'
    assert client.get('/api/v1/workbench/history/unknown').status_code==422
    assert client.post('/api/v1/workbench/history').status_code==405
