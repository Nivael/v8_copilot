import copy,gzip,json
from pathlib import Path
import pytest
from canonical_json import digest
from st_removal_era_comparison import removal_era_comparison,scope_digest

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/removal-era-comparison.json.gz').read_bytes()))
def view(i):return removal_era_comparison(i,i['test_daily'])
def seal(i):
 p=i['removal_era_comparison'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_49_events_do_not_become_a_random_old_new_policy_experiment():
 i=fixture();old=copy.deepcopy(i);v=view(i);assert i==old
 assert(v['total'],v['pre_count'],v['post_count'],len(v['quote_sources']))==(49,37,12,98)
 a=v['summaries']['20']['pre']['from_resume_close'];b=v['summaries']['20']['post']['from_resume_close']
 assert(a['all']['count'],a['all']['positive'],a['all']['negative'],a['all']['cross_rule'])==(36,10,26,22)
 assert(b['all']['count'],b['all']['positive'],b['all']['negative'])==(10,5,5)
 assert a['all']['median_pct']==pytest.approx(-11.930978597645264)and b['all']['median_pct']==pytest.approx(1.139350494189204)
 assert'不是所有ST的摘帽成功率'in v['boundary']and'前组22个窗口跨过'in v['answer']

def test_first_resume_continuation_and_market_windows_are_distinct():
 v=view(fixture());assert(v['first_resume']['pre']['positive'],v['first_resume']['post']['positive'])==(25,5)
 r=next(r for r in v['rows']if r['symbol']=='603580');a=r['windows']['20']['including_resume'];b=r['windows']['20']['from_resume_close'];assert a['anchor']!=b['anchor']and a['through']!=b['through'];assert b['stock_pct']==pytest.approx(132.81124497991968)
 assert r['first_resume']['market_days']==2 and len(r['halt_dates'])==1

def test_no_cross_rule_or_official_source_promotion():
 v=view(fixture());a=v['summaries']['20']['pre']['from_resume_close'];assert a['pure_regime']['count']==14 and a['pure_regime']['cross_rule']==0 and a['official_only']['count']==31
 assert v['summaries']['40']['pre']['from_resume_close']['pure_regime']['count']==0
 assert sum(not r['official_body']for r in v['rows'])==5

def test_gaps_and_individually_bound_corporate_action_support_are_preserved():
 v=view(fixture());r={r['symbol']:r for r in v['rows']};assert r['603517']['windows']['5']['from_resume_close']['support_kind']=='verified_action_factor_reconstruction'
 assert r['603517']['windows']['20']['from_resume_close']['status']=='insufficient_followup'
 assert r['600360']['windows']['20']['from_resume_close']['status']=='factor_basis_unresolved'
 assert r['603580']['windows']['5']['from_resume_close']['status']=='nontraded_or_missing_endpoint'
 assert v['summaries']['40']['pre']['from_resume_close']['paired_count']==0
 assert(v['summaries']['20']['pre']['from_resume_close']['paired_count'],v['summaries']['20']['pre']['from_resume_close']['first_up_then_down'])==(22,18)

@pytest.mark.parametrize('bad',['scope','digest','count','date','calendar','raw_quote','volume','factor','horizon','rule','network','juewei'])
def test_corrupted_scope_or_unbacked_proof_cannot_be_reused(bad):
 i=fixture();p=i['removal_era_comparison']
 if bad=='scope':i['through']='2026-11-05'
 elif bad=='digest':p['version']=2
 elif bad=='count':i['pre_rule_membership']['rows'].pop();seal(i)
 elif bad=='date':i['member_transitions']['rows'][1]['effective_on']='2026-07-07';seal(i)
 elif bad=='calendar':i['dynamic_reference_audit']['original_prices']['companies'][0]['rows'].pop();seal(i)
 elif bad=='raw_quote':i['dynamic_reference_audit']['sources'][0]['sha256']='0'*64;seal(i)
 elif bad=='volume':
  r=next(c for c in i['dynamic_reference_audit']['original_prices']['companies']if c['symbol']=='603580')['rows'][0];r['has_trade']=not r['has_trade'];seal(i)
 elif bad=='factor':next(c for c in i['dynamic_reference_audit']['original_prices']['companies']if c['symbol']=='603580')['rows'][0]['adj_factor']=0;seal(i)
 elif bad=='horizon':p['horizons']=[1,5,20];seal(i)
 elif bad=='rule':p['rule_day']='2026-07-07';seal(i)
 elif bad=='network':p['new_network_queries']=1;seal(i)
 elif bad=='juewei':i['juewei_adjustment']['action']['eligible_cash_per_share']='9';seal(i)
 with pytest.raises((ValueError,KeyError,AssertionError)):view(i)

def test_legacy_never_invents_an_event_comparison():assert removal_era_comparison({},[])is None
