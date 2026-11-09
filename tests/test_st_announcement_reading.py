from pathlib import Path
import gzip,json
from copy import deepcopy
import pytest
from canonical_json import digest
from st_announcement_reading import announcement_reading

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/announcement-reading.json.gz').read_bytes()))
def view(i):return announcement_reading(i,i['test_ann'],lambda e:{'anchor':e['published_on'],'windows':{}})
def seal(i):
 p=i['announcement_reading'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_timeline_union_counts_reports_not_independent_facts_and_old_records_exact():
 i=fixture();old=deepcopy(i);v=view(i);assert i==old
 assert(v['verified_documents'],v['raw_fact_records'],v['deduplicated_event_count'])==(214,207,206)
 assert(v['supplement']['files'],v['supplement']['facts'],v['supplement']['source_pages'])==(10,9,53)
 assert len([e for e in v['verified_events']if e['symbol']=='002514'])==29
 assert all(e['source']['announcement_id']!='1225660310'for e in v['verified_events'])
 for e in i['test_ann']['verified_events']:
  found=next(x for x in v['verified_events']if x['id']==e['id']and x['symbol']==e['symbol']);assert {k:x for k,x in found.items()if k not in ('observation_key','same_company_day_facts')}==e
 same=[e for e in v['verified_events']if e['symbol']=='002514'and e['published_on']=='2026-10-31'];assert len(same)==2 and len({e['observation_key']for e in same})==1
 assert all(e['same_company_day_facts']==2 for e in same)
 assert not v['supplement']['schedule_identity_confirmed']
@pytest.mark.parametrize('bad',['digest','scope','source','published','tokens','duplicate','count','schedule','promotion','page'])
def test_unearned_identity_duplicate_or_scope_rejected(bad):
 i=fixture();p=i['announcement_reading']
 if bad=='digest':p['content_digest']='bad'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='source':p['sources'][0]['announcement_id']='bad'
 elif bad=='published':p['events'][0]['published_on']='2026-09-23'
 elif bad=='tokens':p['events'][0]['tokens']=['T9582','曹思聪']
 elif bad=='duplicate':p['events'][-1]['id']=p['events'][0]['id']
 elif bad=='count':p['events'].pop()
 elif bad=='schedule':p['schedule_identity_confirmed']=True
 elif bad=='promotion':p['method_promotions']=1
 elif bad=='page':p['evidence_pages'][0]['text']='changed'
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)
def test_missing_packet_returns_none():assert announcement_reading({}, {},lambda e:e)is None
