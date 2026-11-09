from pathlib import Path
from copy import deepcopy
import json,gzip
import pytest
from canonical_json import digest
from st_initial_day_corroboration import initial_day_corroboration,selected_catalog_rows
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-day-corroboration.json.gz').read_bytes()))
def seal(i):
 p=i['initial_day_corroboration'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def view(i):return initial_day_corroboration(i,i['test_reading'],lambda e:event_context(e,e['symbol'],i,i['test_daily']),i['test_daily'])
def test_issuer_evidence_increases_timely_reading_not_complete_roster_certification():
 i=fixture();before=deepcopy(i);v,r=view(i);assert i==before
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['verified_companies'],r['supplement']['unique_company_days'])==(275,268,267,110,250)
 assert v['counts']=={'initial_members':150,'timely_before':20,'timely_after':42,'remaining':108,'new_issuer_documents':22,'new_pages':66,'internal_name_conflicts':1,'header_without_conflict':21,'with_specific_conditions':16,'general_state_only':6,'dated_official_full_roster_added':0}
 assert {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 assert next(r for r in v['rows']if r['symbol']=='002977')['internal_name_conflict']
 assert '200016'not in {r['symbol']for r in v['rows']}and len(v['inventory'])==150
 assert next(r for r in v['rows']if r['symbol']=='000016')['full_period']['stock_pct']is None
 assert all(e['observation_key']==e['symbol']+':2026-07-03'for e in v['rows'])
def test_selection_uses_date_venue_title_and_missing_evidence_not_later_return():
 i=fixture();a=selected_catalog_rows(i,i['test_reading']);x=deepcopy(i)
 for r in x['fixed_prices']:r['close']=100000 if r['symbol']=='002977'else 0.01
 for c in x['announcement_study']['catalogs'].values():c['rows'].reverse()
 assert selected_catalog_rows(x,x['test_reading'])==a
@pytest.mark.parametrize('bad',['digest','prior','scope','drop','duplicate','url','source_date','page_hash','header_name','header_code','evidence_page','event_day','event_entity','printed_date','name_conflict','generic_cause','profit_limit','empty_tokens','promotion','full_roster','future_catalog','wrong_market'])
def test_dated_source_conflicts_and_scope_cannot_be_silently_promoted(bad):
 i=fixture();p=i['initial_day_corroboration'];s=p['sources'][0];row=p['rows'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='prior':i['test_reading']['verified_events'].pop()
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='drop':p['sources'].pop()
 elif bad=='duplicate':p['sources'].append(s)
 elif bad=='url':s['url']='https://example.invalid/wrong'
 elif bad=='source_date':s['announcement_date']='2026-07-04'
 elif bad=='page_hash':s['selected_pages']['1']='changed'
 elif bad in('header_name','header_code'):
  from hashlib import sha256
  text=s['selected_pages']['1'].replace('*ST美丽','美丽生态')if bad=='header_name'else s['selected_pages']['1'].replace('000010','000011');s['selected_pages']['1']=text;s['page_hashes'][0]=sha256(text.encode()).hexdigest()
 elif bad=='evidence_page':row['evidence_pages']=[100]
 elif bad=='event_day':row['published_on']='2026-07-04'
 elif bad=='event_entity':row['entity_scope']='shareholder'
 elif bad=='printed_date':row['document_dated_on']='2026-07-03'
 elif bad=='name_conflict':next(r for r in p['rows']if r['symbol']=='002977')['internal_name_conflict']=False
 elif bad=='generic_cause':next(r for r in p['rows']if r['symbol']=='000698')['specific_conditions_present']=True
 elif bad=='profit_limit':row['source_note']='精确利润已核'
 elif bad=='empty_tokens':row['required_source_tokens']=[]
 elif bad=='promotion':p['method_promotions']=1
 elif bad=='full_roster':p['full_membership_certification_added']=True
 elif bad=='future_catalog':i['announcement_study']['catalogs']['000010']['rows'][0]['announcement_date']='2026-07-04'
 elif bad=='wrong_market':
  i['members'].append({'symbol':'200016','name':'*ST康佳B','trade_date':'2026-07-03'});p['scope_digest']=digest({k:i[k]for k in ('calendar','through','members','fixed_prices','benchmarks')});p['rows'][1]['symbol']='200016'
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError,StopIteration)):view(i)
def test_no_packet_does_not_change_prior():assert initial_day_corroboration({}, {'old':1},lambda e:e,[])==(None,{'old':1})
