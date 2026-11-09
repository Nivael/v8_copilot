import copy,json
from pathlib import Path
import pytest
from canonical_json import digest
from st_remaining_basis import remaining_basis_view,scope_digest,apply_remaining_status
from st_regime_comparison import daily_observation

def fixture():return json.loads((Path(__file__).parent/'fixtures/remaining-basis.json').read_text())
def seal(i):
 a=i['fixed_quote_audit'];a['content_digest']=digest({k:v for k,v in a.items()if k!='content_digest'});p=i['remaining_basis'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_eight_rebuilt_with_conflict_and_original_inputs_retained():
 i=fixture();old=copy.deepcopy(i);v=remaining_basis_view(i)
 assert (v['supported_count'],v['price_dates'],v['quote_points'],v['source_conflict_companies'])==(8,1006,2012,1)
 assert (v['new_files'],v['reused_files'],v['source_pages'],v['new_pages'])==(9,2,51,44)
 assert i==old and all(not r['product_mismatch_dates']and not r['normalized_mismatch_dates']for r in v['rows'])
 for r in v['rows']:
  assert all(abs(w['primary_pct']-w['rebuilt_pct'])<1e-10 for w in r['windows'].values())
def test_reorg_reference_over_five_percent_still_equals_cent_boundary():
 i=fixture();r=next(r for r in remaining_basis_view(i)['rows']if r['symbol']=='000793')
 assert r['traded_days']==124 and r['last_actual_date']=='2026-06-17'and r['actual_halt_dates']==['2026-06-18']
 assert r['reference']=='2.51'and float(r['old_up_boundary'])==float(r['ex_raw'])==2.64 and r['reference_day_pct']>5 and not r['above_old_up_boundary']
 assert r['same_cent_difference_dates']==['2026-05-12','2026-05-18']and r['old_holder_distribution']=='0'
 a=next(x for x in i['activities']if x['symbol']=='000793'and x['trade_date']=='2026-06-22');assert daily_observation({'000793':{}},{'000793':a})['beyond_old_up_pct']==0

def test_printed_formula_is_not_silently_corrected():
 r=next(r for r in remaining_basis_view(fixture())['rows']if r['symbol']=='000821');c=r['source_conflict']
 assert c['status']=='unresolved_issuer_formula_denominator'and c['issuer_correction_verified']is False
 assert float(c['literal_per_ten'])==pytest.approx(.33)and c['consistent_per_ten']=='0.326688'
 assert r['eligible_cash_also_matches']and float(r['reference_cash'])==.0326688

@pytest.mark.parametrize('bad',['packet','scope','page','source','publication','cash','amount','shares','precision','conflict_hidden','fake_correction','reorg_shares','reorg_reference','kind','cache','factor','member'])
def test_corruption_does_not_receive_support(bad):
 i=fixture();p=i['remaining_basis'];cash=next(r for r in p['rows']if r['symbol']=='000821');reorg=next(r for r in p['rows']if r['symbol']=='000793')
 if bad=='packet':cash['name']+='x'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='page':p['sources'][0]['selected_pages']['1']+='changed'
 elif bad=='source':cash['cash_source']['sha256']='bad'
 elif bad=='publication':cash['published_on']='2026-06-26'
 elif bad=='cash':cash['per_eligible_share_cash']='0.33'
 elif bad=='amount':cash['declared_total']='20348617.68'
 elif bad=='shares':cash['excluded_shares']='6250001'
 elif bad=='precision':cash['reference_rounding']='unknown'
 elif bad=='conflict_hidden':cash['source_conflict']=None
 elif bad=='fake_correction':cash['source_conflict']['issuer_correction_verified']=True
 elif bad=='reorg_shares':reorg['after_shares']='4393940006'
 elif bad=='reorg_reference':reorg['declared_reference']='2.52'
 elif bad=='kind':reorg['kind']='split'
 elif bad=='cache':p['ex_cache_rows'][0]['row']['pre_close']=1
 elif bad=='factor':i['fixed_quote_audit']['original_prices']['companies'][0]['rows'][0]['adj_factor']=1
 elif bad=='member':i['members']=[x for x in i['members']if not(x['symbol']=='000793'and x['trade_date']=='2026-06-22')]
 if bad not in ('packet','scope'):seal(i)
 with pytest.raises((ValueError,KeyError)):remaining_basis_view(i)

def test_three_old_explanations_and_direct_classification_preserved():
 v=remaining_basis_view(fixture());a={'rows':[{'symbol':s,'qfq_difference_days':1,'basis_reconciled':s not in {r['symbol']for r in v['rows']}}for s in ['603517','002592','002598']+[r['symbol']for r in v['rows']]],'qfq_difference_companies':11,'qfq_agree_companies':137,'answer':'last','previous_answer':'original'}
 apply_remaining_status(a,v,None);assert a['qfq_basis_explained_companies']==11 and a['qfq_unexplained_companies']==0 and a['qfq_agree_companies']==137 and a['qfq_difference_companies']==11 and a['before_remaining_answer']=='last'and a['source_arithmetic_conflict_companies']==1

def test_legacy_has_no_invented_explanation():assert remaining_basis_view({})is None

def test_nonreproduced_quote_is_not_marked_explained():
 from hashlib import sha256
 i=fixture();s=next(s for s in i['fixed_quote_audit']['sources']if s['symbol']=='000793'and s['key']=='tencent_qfq');j=json.loads(s['raw_text']);block=j['data']['sz000793'];bars=block.get('qfqday')or block['day'];bars[0][2]='9.999';s['raw_text']=json.dumps(j);s['sha256']=sha256(s['raw_text'].encode()).hexdigest();seal(i);v=remaining_basis_view(i)
 assert v['supported_count']==7 and v['remaining_unreconstructed']==1
 a={'rows':[{'symbol':'000793','qfq_difference_days':28,'basis_reconciled':False}],'qfq_difference_companies':11,'answer':'old','previous_answer':'first'};apply_remaining_status(a,v,None);assert not a['rows'][0]['basis_reconciled']
