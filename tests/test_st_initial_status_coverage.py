from copy import deepcopy
from pathlib import Path
import gzip,json
import pytest
from canonical_json import digest
from st_initial_status_coverage import initial_status_coverage
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-status-coverage.json.gz').read_bytes()))
def view(i):return initial_status_coverage(i,i['test_reading'],lambda e:event_context(e,e['symbol'],i,i['test_daily']),i['test_daily'])
def seal(i):
 p=i['initial_status_coverage'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_reading_is_not_full_membership_certification_or_six_new_catalysts():
 i=fixture();old=deepcopy(i);v,r=view(i);assert i==old
 assert v['counts']=={'initial_members':150,'timely_reading_before':14,'timely_reading_after':20,'without_timely_reading':130,'new_companies':6,'new_files':6,'new_pages':17,'origin_basis_in_new_documents':4}
 assert len(v['inventory'])==150 and sum(x['has_timely_reading_facts']for x in v['inventory'])==20
 assert v['method_promotions']==0 and not v['full_membership_certification_added']
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['verified_companies'])==(222,215,214,95)
 assert {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 assert all(e['change_kind']=='existing_risk_restatement'and e['same_company_day_facts']==1 for e in v['rows'])
 assert 'ST瑞和' in v['rows'][0]['source_note'] and not v['rows'][1]['origin_basis_in_this_document'] and not v['rows'][-1]['origin_basis_in_this_document']
@pytest.mark.parametrize('bad',['digest','scope','reading','future','identity','header','page','pagination','catalog','repeat','promotion','full_certification','basis_overclaim','missing_cohort'])
def test_changed_source_dates_pages_scope_and_overclaims_are_rejected(bad):
 i=fixture();p=i['initial_status_coverage'];s=p['sources'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='reading':i['test_reading']['verified_events'].pop()
 elif bad=='future':p['rows'][0]['published_on']='2026-07-04'
 elif bad=='identity':p['rows'][0]['symbol']='000001'
 elif bad=='header':p['rows'][0]['name']='ST瑞和'
 elif bad=='page':s['selected_pages']['1']='changed'
 elif bad=='pagination':s['selected_pages'].pop('1')
 elif bad=='catalog':i['announcement_study']['catalogs'][s['symbol']]['rows'][0]['url']='https://invalid.example/a.PDF'
 elif bad=='repeat':p['rows'].append(deepcopy(p['rows'][0]))
 elif bad=='promotion':p['method_promotions']=1
 elif bad=='full_certification':p['full_membership_certification_added']=True
 elif bad=='basis_overclaim':p['rows'][1]['origin_basis_in_this_document']=True
 elif bad=='missing_cohort':p['rows'].pop();p['sources'].pop()
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)
def test_full_period_requires_traded_endpoints_and_uses_common_market_dates():
 i=fixture();v,_=view(i);r=v['rows'][0];assert r['full_period']['market_days']==84
 prices={(x['symbol'],x['trade_date']):x for x in i['fixed_prices']}
 assert r['full_period']['stock_pct']==pytest.approx((prices[r['symbol'],'2026-11-06']['close']/prices[r['symbol'],'2026-07-03']['close']-1)*100)
 prices[r['symbol'],'2026-07-03']['has_trade']=False;p=i['initial_status_coverage'];p['scope_digest']=digest({k:i[k]for k in ('calendar','through','members','fixed_prices')});seal(i)
 v,_=view(i);assert v['rows'][0]['full_period']['stock_pct']is None and v['rows'][0]['observation']['windows']['20']['stock_pct']is None
 assert v['rows'][0]['full_period']['market_pct']is not None

def test_no_packet_is_backward_compatible():assert initial_status_coverage({}, {'old':1},lambda e:e,[])==(None,{'old':1})
