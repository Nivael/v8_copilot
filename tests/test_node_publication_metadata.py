from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
import pytest

from canonical_json import digest
import node_publication_metadata as m

NOW=datetime(2026,11,5,14,tzinfo=timezone.utc)


@pytest.fixture
def capture(tmp_path,monkeypatch):
    folder=tmp_path/'raw';folder.mkdir();code='000001';org='gssz0000001';identifier='1234567890'
    millis=int(datetime(2023,3,1,16,tzinfo=timezone.utc).timestamp())*1000
    row={'announcementId':identifier,'secCode':code,'orgId':org,'announcementTime':millis,'adjunctUrl':'finalpage/2023-03-02/'+identifier+'.PDF','announcementTitle':'关于收到<em>法院</em>文书的公告'}
    responses={'lookup-'+code:[{'code':code,'orgId':org}], 'notice-'+identifier:{'hasMore':False,'totalAnnouncement':1,'announcements':[row]}}
    params={'pageNum':'1','pageSize':'100','column':'szse','tabName':'fulltext','plate':'sz','stock':code+','+org,'searchkey':'','secid':'','category':'','trade':'','seDate':'2023-02-28~2023-03-03','sortName':'','sortType':'','isHLtitle':'true'}
    refs=[{'label':'lookup-'+code,'url':m.LOOKUP,'params':{'keyWord':code,'maxNum':'10'}},{'label':'notice-'+identifier,'url':m.QUERY,'params':params}]
    for r in refs:r.update(response_url=r['url'],method='POST',observed_at='2026-11-05T13:00:00+00:00')
    item={'symbol':code,'source_ref':'cninfo:'+identifier,'event_ids':['E1'],'parent_published_dates':['2023-03-01'],'parent_source_urls':['http://static.cninfo.com.cn/finalpage/2023-03-02/'+identifier+'.PDF'],
          'status':'matched','org_id':org,'lookup_ref':'lookup-'+code,'query_ref':'notice-'+identifier,'announcement_id':identifier,'title':'关于收到法院文书的公告',
          'official_catalog_date':'2023-03-02','announcement_time_raw_ms':millis,'attachment_path':'/finalpage/2023-03-02/'+identifier+'.PDF','query_start':'2023-02-28','query_end':'2023-03-03'}
    profile={'version':m.VERSION,'p6_run':{'run_id':'active','as_of':'2026-07-20','verified_event_count':2},'capture_completed_at':'2026-11-05T13:01:00+00:00',
             'frame_document_items':2,'frame_events':2,'frame_companies':1,'metadata_refs':refs,'items':[item,{'symbol':code,'source_ref':'cninfo:AN1','event_ids':['E2'],'status':'noncanonical_source_id'}]}
    path=tmp_path/'profile.json';monkeypatch.setattr(m,'PROFILE',profile);monkeypatch.setattr(m,'PROFILE_PATH',path)
    def bind():
        for r in profile['metadata_refs']:
            b=json.dumps(responses[r['label']],ensure_ascii=False).encode();r.update(response_sha256=sha256(b).hexdigest(),bytes=len(b));(folder/(r['response_sha256']+'.json')).write_bytes(b)
        path.write_text(json.dumps(profile));monkeypatch.setattr(m,'PROFILE_DIGEST',digest(profile))
    bind();return folder,profile,responses,bind


def test_catalog_milliseconds_are_beijing_date_not_utc_date_or_exact_release_instant(capture):
    folder,p,_,_=capture;r=m.metadata_status(p['p6_run'],folder,NOW)
    assert r['availability']=='observed' and (r['matched_documents'],r['matched_events'],r['unbound_documents'],r['metadata_responses'])==(1,1,1,2)
    row=r['reviews'][0]
    assert row['official_catalog_date']=='2023-03-02' and row['parent_published_dates']==['2023-03-01']
    assert row['utc_interpretation_date']=='2023-03-01' and row['utc_date_matches_parent'] is True and row['changed_from_parent_date'] is True
    assert r['historical_PIT'] is r['full_body_semantics_checked'] is r['exact_release_timestamps_verified'] is False
    assert m.catalog_day(1656691200000)=='2022-07-02'


@pytest.mark.parametrize('bad',['company','org','id','attachment','title','millis_string','millis_bool','date','extra_page','total','duplicate','query_scope','query_company','query_method','query_url','redirect','lookup_org','lookup_duplicate','old_date_bounds','old_date_non_iso','future','naive','capture_before_response','event_duplicate','frame_count','parent_attachment','foreign_profile'])
def test_rehashed_wrong_identity_time_query_paging_or_frame_never_keeps_old_date_claim(capture,bad):
    folder,p,responses,bind=capture;ref=p['metadata_refs'][1];rows=responses[ref['label']]['announcements'];row=rows[0];item=p['items'][0]
    if bad=='company':row['secCode']='999999'
    elif bad=='org':row['orgId']='another'
    elif bad=='id':row['announcementId']='9999999999'
    elif bad=='attachment':row['adjunctUrl']=row['adjunctUrl'].replace('1234567890','9999999999')
    elif bad=='title':row['announcementTitle']='另一公告'
    elif bad=='millis_string':row['announcementTime']=str(row['announcementTime'])
    elif bad=='millis_bool':row['announcementTime']=True
    elif bad=='date':row['announcementTime']-=86400000
    elif bad=='extra_page':responses[ref['label']]['hasMore']=True
    elif bad=='total':responses[ref['label']]['totalAnnouncement']=2
    elif bad=='duplicate':rows.append(deepcopy(row));responses[ref['label']]['totalAnnouncement']=2
    elif bad=='query_scope':ref['params']['searchkey']='重整'
    elif bad=='query_company':ref['params']['stock']='999999,another'
    elif bad=='query_method':ref['method']='GET'
    elif bad=='query_url':ref['url']=ref['response_url']='https://example.com/query'
    elif bad=='redirect':ref['response_url']='https://example.com/query'
    elif bad=='lookup_org':responses[p['metadata_refs'][0]['label']][0]['orgId']='another'
    elif bad=='lookup_duplicate':responses[p['metadata_refs'][0]['label']]*=2
    elif bad=='old_date_bounds':item['parent_published_dates']=['2024-01-01']
    elif bad=='old_date_non_iso':item['parent_published_dates']=['20230301']
    elif bad=='future':ref['observed_at']='2026-11-06T00:00:00+00:00'
    elif bad=='naive':ref['observed_at']='2026-11-05T13:00:00'
    elif bad=='capture_before_response':p['capture_completed_at']='2026-11-05T12:00:00+00:00'
    elif bad=='event_duplicate':p['items'][1]['event_ids']=['E1']
    elif bad=='frame_count':p['frame_events']=3
    elif bad=='parent_attachment':item['parent_source_urls']=['https://example.com'+item['attachment_path']]
    elif bad=='foreign_profile':p['version']='other'
    bind();r=m.metadata_status(p['p6_run'],folder,NOW)
    assert r['availability']=='invalid' and r['reviews']==[] and r['matched_documents'] is None


def test_missing_or_changed_bytes_profile_and_active_source_frame_never_reuse_old_counts(capture):
    folder,p,_,_=capture;ref=p['metadata_refs'][1];path=folder/(ref['response_sha256']+'.json');before=path.read_bytes();path.write_bytes(b'changed')
    assert m.metadata_status(p['p6_run'],folder,NOW)['availability']=='invalid';path.write_bytes(before)
    assert m.metadata_status({**p['p6_run'],'run_id':'new'},folder,NOW)['availability']=='source_frame_changed'
    m.PROFILE_PATH.write_text('{}');assert m.metadata_status(p['p6_run'],folder,NOW)['availability']=='invalid'
