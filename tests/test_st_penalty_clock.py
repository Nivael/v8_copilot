from pathlib import Path
from copy import deepcopy
import json,gzip
import pytest
from canonical_json import digest
from st_penalty_clock import penalty_clock
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-penalty-clock.json.gz').read_bytes()))
def view(i):return penalty_clock(i,i['test_reading'],i['test_origin'],i['test_day'],lambda e:event_context(e,e['symbol'],i,i['test_daily']))
def seal(i):
 p=i['penalty_clock'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_dates_not_receipt_and_materials_not_repeated_events():
 i=fixture();before=deepcopy(i);v,r=view(i);assert i==before
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['supplement']['unique_company_days'])==(290,281,280,263)
 assert {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 assert len(v['rows'])==3 and sum(len(r['supporting_sources'])for r in v['rows'])==2
 c={c['symbol']:c for c in v['companies']};assert (c['000698']['decision_made_on'],c['000698']['received_on'],c['000698']['anniversary_reference'],c['000698']['days_to_reference_at_cutoff'])==('2025-11-25','2025-11-28','2026-11-25',19)
 assert c['002586']['anniversary_reference']=='2026-04-29' and v['stages']['days_reference_to_board']==105 and v['stages']['days_reference_to_effective']==124
 assert v['stages']['independent_approval_letter_obtained']is False
 assert v['removal_event']['observation']['windows']['5']['stock_pct']is None
 assert v['effective_observation']['anchor']=='2026-08-31' and v['application']['observation']['anchor']=='2026-08-13'
 assert c['000698']['regulator']['page_metadata_pubdate'].startswith('2026-08-01')
@pytest.mark.parametrize('bad',['digest','prior','origin','day','scope','promotion','roster','drop','duplicate','source_date','page','meta_date','meta_url','meta_code','reg_date','reg_url','reg_body','reg_pubdate','reg_history','replay_sha','replay_page','event_day','printed_date','entity','evidence_page','duplicate_row'])
def test_conflicts_cannot_be_hidden_by_resigning_packet(bad):
 i=fixture();p=i['penalty_clock'];s=p['sources'][0];reg=p['regulators'][0];r=p['rows'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='prior':i['test_reading']['verified_events'].pop()
 elif bad=='origin':i['test_origin']['cases'].pop()
 elif bad=='day':i['test_day']['rows'].pop()
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='promotion':p['method_promotions']=1
 elif bad=='roster':p['full_membership_certification_added']=True
 elif bad=='drop':p['sources'].pop()
 elif bad=='duplicate':p['sources'].append(s)
 elif bad=='source_date':s['announcement_date']='2025-11-28'
 elif bad=='page':s['selected_pages']['1']='changed'
 elif bad=='meta_date':s['metadata']['announcementTime']+=86400000
 elif bad=='meta_url':s['url']='https://example.invalid'
 elif bad=='meta_code':s['metadata']['secCode']='002586'
 elif bad=='reg_date':reg['decision_made_on']='2025-11-28'
 elif bad=='reg_url':reg['url']='https://example.invalid'
 elif bad=='reg_body':reg['normalized_text']='changed'
 elif bad=='reg_pubdate':reg['page_metadata_pubdate']=''
 elif bad=='reg_history':reg['historical_availability_basis']=''
 elif bad=='replay_sha':p['removal_replay']['sha256']='changed'
 elif bad=='replay_page':p['removal_replay']['selected_pages']['1']='changed'
 elif bad=='event_day':r['published_on']='2025-11-28'
 elif bad=='printed_date':r['document_dated_on']='2025-11-29'
 elif bad=='entity':r['entity_scope']='shareholder'
 elif bad=='evidence_page':r['evidence_pages']=[99]
 elif bad=='duplicate_row':p['rows'].append(r)
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)
def test_absence_retains_legacy():assert penalty_clock({}, {'old':1},None,None,None)==(None,{'old':1})
