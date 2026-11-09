from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_initial_warning_origin import initial_warning_origin
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-warning-origin.json.gz').read_bytes()))
def run(i):return initial_warning_origin(i,i['test_reading'],i['test_day'],lambda e:event_context(e,e['symbol'],i,i['test_daily']))
def seal(i):
 p=i['initial_warning_origin'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_grounds_close_six_missing_explanations_without_inflating_timely_coverage():
 i=fixture();old=deepcopy(i);v,r=run(i);assert i==old
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['verified_companies'],r['supplement']['unique_company_days'])==(285,278,277,110,260)
 assert v['counts']=={'new_files':10,'new_pages':35,'resolved_general_notice_basis':6,'cases':7,'timely_reading':42,'remaining_timely':108,'pre_calendar_documents':9,'full_membership_certification_added':0}
 assert {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 for c in v['cases']:
  base=next(r for r in i['test_day']['rows']if r['symbol']==c['symbol']);assert c['observation']==base['observation']and c['full_period']==base['full_period']
 dates={e['source']['announcement_id']:e['document_dated_on']for e in v['rows']};assert all(dates.values());assert {k:dates[k]for k in ('1224696715','1224888881','1223155412')}=={'1224696715':'2025-09-30','1224888881':'2025-12-20','1223155412':'2025-04-19'}
 assert next(c for c in v['cases']if c['symbol']=='002977')['internal_conflict_unresolved']
 assert next(c for c in v['cases']if c['symbol']=='000016')['full_period']['stock_pct']is None
 assert all(e['observation']['anchor']is None for e in v['rows']if e['background_only'])
 assert len([e for e in v['rows']if not e['background_only']])==1
@pytest.mark.parametrize('bad',['digest','prior','prior_day','scope','promotion','full_roster','drop','duplicate_source','metadata_id','metadata_code','utc_date','url','title','page','missing_pages','clause','event_day','event_id','entity','printed_date','evidence_page','effective_date','case_source','duplicate_case','name_conflict'])
def test_source_time_scope_and_unresolved_conflict_are_enforced(bad):
 i=fixture();p=i['initial_warning_origin'];s=p['sources'][0];r=p['rows'][0];c=p['cases'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='prior':i['test_reading']['verified_events'].pop()
 elif bad=='prior_day':i['test_day']['rows'].pop()
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='promotion':p['method_promotions']=1
 elif bad=='full_roster':p['full_membership_certification_added']=True
 elif bad=='drop':p['sources'].pop()
 elif bad=='duplicate_source':p['sources'].append(s)
 elif bad=='metadata_id':s['raw_item']['announcementId']='wrong'
 elif bad=='metadata_code':s['raw_item']['secCode']='200016'
 elif bad=='utc_date':s['announcement_date']='2026-04-28'
 elif bad=='url':s['url']='https://example.invalid'
 elif bad=='title':s['title']='different'
 elif bad=='page':s['selected_pages']['1']='changed'
 elif bad=='missing_pages':s['selected_pages'].pop('1')
 elif bad=='clause':
  from hashlib import sha256
  s['selected_pages']={n:t.replace('持续经营重大不确定性','不存在风险')for n,t in s['selected_pages'].items()};s['page_hashes']=[sha256(s['selected_pages'][str(n)].encode()).hexdigest()for n in range(1,s['pages']+1)]
 elif bad=='event_day':r['published_on']='2026-04-30'
 elif bad=='event_id':r['id']='wrong'
 elif bad=='entity':r['entity_scope']='shareholder'
 elif bad=='printed_date':r['document_dated_on']='2026-04-28'
 elif bad=='evidence_page':r['evidence_pages']=[99]
 elif bad=='effective_date':c['effective_on']='2026-04-29'
 elif bad=='case_source':c['source_ids']=['1223155412']
 elif bad=='duplicate_case':p['cases'].append(c)
 elif bad=='name_conflict':next(c for c in p['cases']if c['symbol']=='002977')['internal_conflict_unresolved']=False
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):run(i)
def test_absent_packet_is_backwards_compatible():assert initial_warning_origin({}, {'old':1},None,None)==(None,{'old':1})
