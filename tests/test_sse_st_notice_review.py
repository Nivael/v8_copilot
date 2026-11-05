from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from canonical_json import digest
import sse_st_notice_review as m

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


def put(folder, value):
    raw = json.dumps(value, ensure_ascii=False).encode(); key = hashlib.sha256(raw).hexdigest()
    (folder/(key+'.json')).write_bytes(raw)
    return {'sha256':key, 'bytes':len(raw), 'observed_at':'2026-11-05T10:00:00+00:00'}


@pytest.fixture
def capture(tmp_path, monkeypatch):
    folder = tmp_path/'catalogs'; folder.mkdir(); docs = tmp_path/'documents'; docs.mkdir()
    items = deepcopy([m.PROFILE['events'][i] for i in (0,26,27,48,56,57)])
    transitions = deepcopy(m.TRANSITIONS)
    for item in items:
        pages = [f"证券代码：{item['symbol']}证券简称：{item['name_as_reported']}公告编号：2026-001{item['company']}"] + ['本页资料']*(max(p['page'] for p in item['proofs'])-1)
        for p in item['proofs']: pages[p['page']-1] += '。'+p['text']+'。'
        raw = ('%PDF-synthetic-test-'+item['symbol']).encode(); text = json.dumps({'pages':pages}, ensure_ascii=False).encode()
        item.update(raw_sha256=hashlib.sha256(raw).hexdigest(),text_sha256=hashlib.sha256(text).hexdigest(),raw_bytes=len(raw),text_bytes=len(text),page_count=len(pages))
        (docs/(item['raw_sha256']+'.pdf')).write_bytes(raw); (docs/(item['text_sha256']+'.json')).write_bytes(text)
        for e in transitions:
            if (e['symbol'],e['published_on']) == (item['symbol'],item['published_on']):
                e.update(raw_sha256=item['raw_sha256'],text_sha256=item['text_sha256'])
    catalog = deepcopy(m.CATALOG); catalog['items'] = [{k:r[k] for k in ('symbol','published_on','title','catalog_url')} for r in items]
    rows = [{'SECURITY_CODE':r['symbol'],'SSEDATE':r['published_on'],'TITLE':r['title'],'URL':r['catalog_url'].removeprefix('https://www.sse.com.cn')} for r in items]
    catalog['source_ref'].update(put(folder,{'result':[rows],'pageHelp':{'pageCount':1,'total':len(rows)}}))
    profile = deepcopy(m.PROFILE); profile.update(events=items,catalog_items=len(items),metadata_refs=[])
    for item in items:
        code, org = item['symbol'], item['org_id']
        lookup = {'method':'POST','url':m.LOOKUP,'params':{'keyWord':code,'maxNum':'10'},**put(folder,[{'code':code,'orgId':org}])}
        params = {'pageNum':'1','pageSize':'100','column':'sse','tabName':'fulltext','plate':'sh','stock':code+','+org,'searchkey':'风险警示','secid':'','category':'','trade':'',
                  'seDate':'2026-09-01~2026-11-04','sortName':'','sortType':'','isHLtitle':'true'}
        record = {'secCode':code,'orgId':org,'announcementId':item['announcement_id'],'announcementTitle':item['cninfo_title'],
                  'adjunctUrl':item['source_url'].removeprefix('https://static.cninfo.com.cn/')}
        query = {'method':'POST','url':m.QUERY,'params':params,**put(folder,{'announcements':[record],'hasMore':False,'totalAnnouncement':1})}
        profile['metadata_refs'].extend([lookup,query])
    monkeypatch.setattr(m,'PROFILE',profile);monkeypatch.setattr(m,'CATALOG',catalog);monkeypatch.setattr(m,'TRANSITIONS',transitions)
    return tmp_path


def test_cross_catalog_identity_dates_and_status_roles_stay_separate(capture):
    data=m.project(m.collect_inputs(capture,now=NOW))
    assert data['availability']=='reviewed' and data['reviewed_items']==data['catalog_items']==6
    assert data['counts']==dict(warning_added=1,warning_removed=1,application_pending=1,layered_warning_existing_member=1,existing_warning_described=2)
    pending=next(r for r in data['items'] if r['kind']=='application_pending')
    assert pending['effective_on'] is None and pending['published_on']=='2026-10-24'
    assert next(r for r in data['items'] if r['kind']=='layered_warning_existing_member')['stated_since_on']=='2026-07-07'
    assert all(data[k] is False for k in ('full_body_semantics_reviewed','full_window_membership_certificate','historical_membership_verified','historical_PIT','combined_ST_ready','effect_measured'))


@pytest.mark.parametrize('bad',['bytes','text','company','name','physical_page','clause','since_date_role','pending_effective',
    'promote_application','promote_layer','transition_date','transition_kind','metadata_method','query_scope','missing_lookup','duplicate_query',
    'sse_catalog_scope','catalog_identity','incomplete_page','duplicate_notice','wrong_org','metadata_title','future_observation'])
def test_unbound_or_reclassified_evidence_cannot_publish(capture,bad):
    item=m.PROFILE['events'][0]; query=m.PROFILE['metadata_refs'][1]
    if bad=='bytes': (capture/'documents'/(item['raw_sha256']+'.pdf')).write_bytes(b'%PDF-modified')
    elif bad=='text': (capture/'documents'/(item['text_sha256']+'.json')).write_bytes(b'{}')
    elif bad=='company': item['company']='另一家公司股份有限公司'
    elif bad=='name': item['name_as_reported']='ST其他'
    elif bad=='physical_page': item['proofs'][0]['page']=2
    elif bad=='clause': item['proofs'][0]['text']='公司股票于2026年9月1日起被实施其他风险警示'
    elif bad=='since_date_role': item['stated_since_on']='2026-04-29'
    elif bad=='pending_effective': m.PROFILE['events'][1]['effective_on']='2026-10-24'
    elif bad=='promote_application': m.PROFILE['events'][1]['kind']='warning_removed'
    elif bad=='promote_layer': m.PROFILE['events'][4]['kind']='warning_added'
    elif bad=='transition_date': m.PROFILE['events'][2]['effective_on']='2026-10-19'
    elif bad=='transition_kind': m.PROFILE['events'][2]['kind']='warning_added'
    elif bad=='metadata_method': query['method']='GET'
    elif bad=='query_scope': query['params']['searchkey']='撤销'
    elif bad=='missing_lookup': m.PROFILE['metadata_refs'].pop(0)
    elif bad=='duplicate_query': m.PROFILE['metadata_refs'].append(deepcopy(query))
    elif bad=='sse_catalog_scope': m.CATALOG['source_ref']['params']['SECURITY_CODE']='600080'
    elif bad=='catalog_identity': m.CATALOG['items'][0]['symbol']='600099'
    elif bad=='future_observation': item['observed_at']='2026-11-07T10:00:00+00:00'
    else:
        data=json.loads((capture/'catalogs'/(query['sha256']+'.json')).read_text())
        if bad=='incomplete_page':data['hasMore']=True
        elif bad=='duplicate_notice':data['announcements']*=2;data['totalAnnouncement']=2
        elif bad=='wrong_org':data['announcements'][0]['orgId']='another'
        else:data['announcements'][0]['announcementTitle']='无关公告'
        query.update(put(capture/'catalogs',data))
    with pytest.raises((ValueError,KeyError)):m.collect_inputs(capture,now=NOW)


def test_a_cited_title_or_future_condition_cannot_be_used_as_a_prior_warning():
    item=deepcopy(m.PROFILE['events'][0])
    for text in ['公司于2026年4月29日披露的《关于实施其他风险警示的公告》','若公司股票于2026年4月30日起可能被实施其他风险警示']:
        item['proofs'][0]['text']=text
        with pytest.raises(ValueError,match='forecast or cited title'):m.verify_roles(item)


def test_chinese_publication_day_is_not_mistaken_for_utc_day(capture):
    m.PROFILE['events'][0]['observed_at']='2026-10-30T17:00:00+00:00'
    assert m.collect_inputs(capture,now=NOW)['items'][0]['published_on']=='2026-10-31'
    m.PROFILE['events'][0]['observed_at']='2026-10-30T12:00:00+00:00'
    with pytest.raises(ValueError,match='chronology'):m.collect_inputs(capture,now=NOW)


def test_readonly_snapshot_recomputes_and_ignores_injected_certification(capture,tmp_path,monkeypatch):
    inputs=m.collect_inputs(capture,now=NOW);monkeypatch.setattr(m,'collect_inputs',lambda *a,**k:deepcopy(inputs))
    output=tmp_path/'published';m.materialize(output,now=NOW);path=output/'current.json'
    raw=json.loads(path.read_text());raw['report']={'combined_ST_ready':True,'reviewed_items':999,'full_body_semantics_reviewed':True}
    raw['content_digest']=digest({k:v for k,v in raw.items() if k!='content_digest'});path.write_text(json.dumps(raw));before=path.read_bytes()
    data=m.review_status(output,now=NOW)
    assert data['reviewed_items']==6 and data['combined_ST_ready'] is data['full_body_semantics_reviewed'] is False
    assert path.read_bytes()==before
    inputs['items'][0]['observed_at']='changed'
    assert m.review_status(output,now=NOW)['availability']=='invalid' and path.read_bytes()==before


def test_sources_or_processor_changing_during_recheck_preserve_current(capture,tmp_path,monkeypatch):
    inputs=m.collect_inputs(capture,now=NOW);monkeypatch.setattr(m,'collect_inputs',lambda *a,**k:deepcopy(inputs))
    output=tmp_path/'published';m.materialize(output,now=NOW);path=output/'current.json';before=path.read_bytes()
    changed=deepcopy(inputs);changed['items'].pop();seq=iter([inputs,changed])
    monkeypatch.setattr(m,'collect_inputs',lambda *a,**k:next(seq))
    with pytest.raises(ValueError,match='sources or processor'):m.materialize(output,now=NOW)
    assert path.read_bytes()==before
    def read(*a,**k):
        if not k.get('full'):monkeypatch.setattr(m,'processor_digest',lambda:'changed-after-collection')
        return deepcopy(inputs)
    monkeypatch.setattr(m,'collect_inputs',read)
    with pytest.raises(ValueError,match='sources or processor'):m.materialize(output,now=NOW)
    assert path.read_bytes()==before
    monkeypatch.setattr(m,'processor_digest',lambda:m.PROCESSOR);path.write_text('{"version":"foreign"}');before=path.read_bytes()
    with pytest.raises(ValueError,match='foreign'):m.materialize(output,now=NOW)
    assert path.read_bytes()==before


def test_notice_clause_coverage_is_not_ST_venue_or_effectiveness_coverage(tmp_path,monkeypatch):
    import market_risk
    fake={'availability':'reviewed','through':'2026-11-04','reviewed_items':62,'catalog_items':62,'historical_membership_verified':False}
    monkeypatch.setattr(market_risk,'sse_st_notice_status',lambda *a,**k:deepcopy(fake))
    data=market_risk.build_market_risk_status(snapshot_dir=tmp_path,database=tmp_path/'missing.db',manifest_path=tmp_path/'missing.json',now=NOW)
    assert data['market_coverage']['st_style_at_target'] is False and data['market_coverage']['st_reference_venues_at_target']==0
    assert data['market_coverage']['st_reconstruction_source_venues_at_target']==0 and data['parameters']['risk_weights'] is None
    row=next(r for r in market_risk.market_update_status(snapshot_dir=tmp_path,now=NOW) if r['source_id']=='sse_ST_notice_clauses')
    assert row['coverage_basis']=='ST_notice_clause_review' and row['observed_source_groups']==row['declared_series']==62
    assert row['series_at_target'] is None and row['observation_unit']=='目录项'
