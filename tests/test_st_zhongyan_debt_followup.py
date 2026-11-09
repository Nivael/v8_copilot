from pathlib import Path
from copy import deepcopy
import json,gzip
import pytest
from canonical_json import digest
from st_zhongyan_debt_followup import zhongyan_debt_followup
from st_regime_themes import event_context

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-zhongyan-debt-followup.json.gz').read_bytes()))
def seal(i):
 p=i['zhongyan_debt_followup'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def view(i):return zhongyan_debt_followup(i,i['test_reading'],i['test_three'],lambda e:event_context(e,e['symbol'],i,i['test_daily']))
def test_approval_closes_old_pending_without_certifying_new_money_or_waiver():
 i=fixture();before=deepcopy(i);v,r=view(i);assert i==before
 assert v['claims']['approved']and not v['claims']['ceiling_all_paid_verified']and not v['claims']['debt_waived']
 assert v['claims']['meeting_on']=='2026-09-17'and v['claims']['published_on']=='2026-09-18'
 assert (r['verified_documents'],r['raw_fact_records'],r['deduplicated_event_count'],r['verified_companies'],r['supplement']['unique_company_days'])==(253,246,245,95,228)
 assert {e['id']:e for e in i['test_reading']['verified_events']}.items()<={e['id']:e for e in r['verified_events']}.items()
 assert (v['new_files'],v['new_pages'],v['selected_pages'])==(2,6,11)
 b={r['key']:r for r in v['balances']};assert b['liabilities']['change']=='-306831443.77'and b['other_payables']['change']=='735106613.00'and b['short_borrowing']['change']=='-459482308.23'
 assert b['parent_equity']['after']=='-511713101.23'and not v['claims']['quarter_audited']
@pytest.mark.parametrize('bad',['digest','prior_reading','prior_three','scope','source_issuer','source_day','page_hash','catalog','quarter_identity','quarter_pages','paid','ceiling','all_paid','waiver','current_balance','receipt','court','audited','balance_unit','balance_period','balance_sign','balance_row','event_stage','event_entity','duplicate_source','promotion','comparator'])
def test_source_approval_and_balance_boundaries_cannot_be_substituted(bad):
 i=fixture();p=i['zhongyan_debt_followup'];s=p['sources'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad=='prior_reading':i['test_reading']['verified_events'].pop()
 elif bad=='prior_three':i['test_three']['rows'].pop()
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='source_issuer':s['symbol']='000639'
 elif bad=='source_day':s['announcement_date']='2026-09-17'
 elif bad=='page_hash':s['selected_pages']['1']='changed'
 elif bad=='catalog':s['url']='https://example.invalid/not-the-source'
 elif bad=='quarter_identity':p['replayed_quarter']['sha256']='bad'
 elif bad=='quarter_pages':p['replayed_quarter']['selected_pages'].pop('5')
 elif bad=='paid':p['claims']['bond_paid_yuan']='638741589.98'
 elif bad=='ceiling':p['claims']['approved_ceiling_yuan']='1157241589.98'
 elif bad=='all_paid':p['claims']['ceiling_all_paid_verified']=True
 elif bad=='waiver':p['claims']['debt_waived']=True
 elif bad=='current_balance':p['claims']['current_shareholder_balance_verified']=True
 elif bad=='receipt':p['claims']['bank_receipt_or_clearing_direct_verified']=True
 elif bad=='court':p['claims']['court_acceptance_verified']=True
 elif bad=='audited':p['claims']['quarter_audited']=True
 elif bad=='balance_unit':p['balance_unit']='wan'
 elif bad=='balance_period':p['balance_periods'][0]='2026-06-30'
 elif bad=='balance_sign':p['balances']['parent_equity'][1]='511713101.23'
 elif bad=='balance_row':p['balances']['other_payables'][1]='638741589.98'
 elif bad=='event_stage':p['rows'][0]['change_kind']='court_accepted'
 elif bad=='event_entity':p['rows'][0]['entity_scope']='shareholder'
 elif bad=='duplicate_source':p['sources'].append(s)
 elif bad=='promotion':p['method_promotions']=1
 elif bad=='comparator':i['warning_basis_followup']['sources'][0]['selected_pages']={'1':'another claim'}
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)
def test_two_new_nodes_all_six_windows_keep_same_dates_and_cached_price_checks():
 v,_=view(fixture());assert len(v['rows'])==2
 assert all(w['agreement_to_2dp']for r in v['rows']for w in r['quote_replay'].values())
 assert all(w['through']for r in v['rows']for w in r['observation']['windows'].values())

def test_no_packet_does_not_change_prior_reading():assert zhongyan_debt_followup({}, {'old':1},None,lambda e:e)==(None,{'old':1})
