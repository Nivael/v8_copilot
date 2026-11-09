import copy,json
from pathlib import Path
import pytest
from hashlib import sha256
from canonical_json import digest
from st_dividend_basis import dividend_basis_view,update_quote_audit,scope_digest
from st_regime_comparison import daily_observation

def fixture():return json.loads((Path(__file__).parent/'fixtures/dividend-basis.json').read_text())
def seal(i):
 a=i['fixed_quote_audit'];a['content_digest']=digest({k:v for k,v in a.items()if k!='content_digest'});p=i['dividend_basis'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_three_actions_rebuild_two_issuers_without_hiding_direct_differences():
 i=fixture();old=copy.deepcopy(i);v=dividend_basis_view(i);assert v['supported'] and v['price_dates']==252 and v['direct_quote_points']==504 and v['primary_pages']==10
 assert [r['direct_difference_days']for r in v['rows']]==[29,51];assert all(not r['additive_mismatch_dates']and not r['normalized_mismatch_dates']for r in v['rows']);assert i==old
 assert all(abs(r['windows']['all']['primary_pct']-r['windows']['all']['rebuilt_pct'])<1e-10 for r in v['rows'])
def test_may_adjusted_five_percent_is_not_old_boundary_breach():
 i=fixture();v=dividend_basis_view(i);a=v['rows'][1]['actions'][0];assert a['direct_qfq_day_pct']>5 and a['reference_day_pct']<5 and a['old_up_boundary']=='7.79' and float(a['ex_raw'])==7.79 and not a['above_old_up_boundary'] and a['at_old_up_boundary'];assert a['remaining_future_cash']=='0.1'
 activity=next(r for r in i['activities']if r['symbol']=='002592'and r['trade_date']==a['ex_on']);result=daily_observation({'002592':{}},{'002592':activity});assert result['beyond_old_up_pct']==0

def test_additional_shares_change_total_not_per_share_amount():
 v=dividend_basis_view(fixture());a=v['rows'][1]['actions'][1];assert a['added_shares']=='55000' and a['total_increase']=='5500' and a['cash_per_share']=='0.1';assert all(not a['shares_final_verified']for r in v['rows']for a in r['actions'])

@pytest.mark.parametrize('bad',['packet','scope','pages','source','cash','ten','shares','record','publication','final','increase','factor','raw','cache','activity','source_set'])
def test_mutated_source_or_calculation_is_not_certified(bad):
 i=fixture();p=i['dividend_basis'];a=p['actions'][0]
 if bad=='packet':a['share_note']+='x'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='pages':p['sources'][0]['selected_pages']['1']+='changed'
 elif bad=='source':a['cash_source']['sha256']='wrong'
 elif bad=='cash':a['cash_per_share']='1'
 elif bad=='ten':a['cash_per_ten']='10'
 elif bad=='shares':a['shares']='312052979'
 elif bad=='record':a['record_on']='2026-07-08'
 elif bad=='publication':a['published_on']='2026-07-02'
 elif bad=='final':a['shares_final_verified']=True
 elif bad=='increase':p['actions'][2]['added_shares']='55001'
 elif bad=='factor':i['fixed_quote_audit']['original_prices']['companies'][0]['rows'][0]['adj_factor']=2
 elif bad=='raw':i['fixed_quote_audit']['original_prices']['companies'][0]['rows'][0]['raw_close']=1
 elif bad=='cache':p['ex_date_cache_rows'][0]['row']['pre_close']=6.7
 elif bad=='activity':next(r for r in i['activities']if r['symbol']=='002598'and r['trade_date']==a['ex_on'])['pre_close']=6.7
 elif bad=='source_set':p['sources'].append(copy.deepcopy(p['sources'][0]))
 if bad not in ('packet','scope'):seal(i)
 with pytest.raises((ValueError,KeyError)):dividend_basis_view(i)

def test_nonreproducible_additive_series_stays_unresolved():
 i=fixture();s=next(s for s in i['fixed_quote_audit']['sources']if s['key']=='tencent_qfq');x=json.loads(s['raw_text']);block=next(iter(x['data'].values()));key='qfqday'if 'qfqday'in block else'day';block[key][0][2]='6.99';s['raw_text']=json.dumps(x);s['sha256']=sha256(s['raw_text'].encode()).hexdigest();seal(i);v=dividend_basis_view(i);assert not v['supported']and any(r['additive_mismatch_dates']for r in v['rows'])

def test_audit_update_retains_direct_categories_and_historical_answer():
 v=dividend_basis_view(fixture());audit={'rows':[{'symbol':'603517','qfq_difference_days':100,'basis_reconciled':True},{'symbol':'002598','qfq_difference_days':29,'basis_reconciled':False},{'symbol':'002592','qfq_difference_days':51,'basis_reconciled':False}],'qfq_difference_companies':11,'qfq_agree_companies':137,'answer':'old'};update_quote_audit(audit,v);assert audit['qfq_basis_explained_companies']==3 and audit['qfq_unexplained_companies']==8 and audit['qfq_agree_companies']==137 and audit['qfq_difference_companies']==11 and audit['previous_answer']=='old'
def test_legacy_snapshot_has_no_invented_action():assert dividend_basis_view({})is None


def test_old_band_example_requires_st_membership_that_day():
 i=fixture();i['members']=[r for r in i['members']if not(r['symbol']=='002592'and r['trade_date']=='2026-05-19')];seal(i)
 with pytest.raises(ValueError,match='membership'):dividend_basis_view(i)
