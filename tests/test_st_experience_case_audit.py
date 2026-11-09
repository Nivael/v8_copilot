from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_experience_case_audit import experience_case_audit,seal_packet

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/experience-case-audit.json.gz').read_bytes()))
def view(i):return experience_case_audit(i,i['test_comparison'],i['test_announcements'])
def seal(i):i['experience_case_audit']=seal_packet(i,i['test_comparison'],i['test_announcements'],'prior')

def test_different_companies_do_not_multiply_with_windows_or_files():
 i=fixture();old=deepcopy(i);v=view(i);assert i==old
 assert tuple(v['counts'][k]for k in ('companies','events','horizons','followup_measurements','valid_followup_measurements','primary_documents','reused_action_support_documents','corpus_documents','corpus_fact_records','corpus_reading_items'))==(49,49,3,147,142,49,6,204,198,197)
 assert len(next(r for r in v['rows']if r['symbol']=='603517')['follow']['5']['action_source_ids'])==3
 assert len(next(r for r in v['rows']if r['symbol']=='600360')['follow']['20']['action_source_ids'])==1
 assert v['method_promotions']==0 and v['new_network_queries']==0
 assert v['repeated_reading_records']==[{'symbol':'002856','event_id':'meizhi_investment','event_key':v['repeated_reading_records'][0]['event_key'],'source_records':2,'distinct_source_files':1}]

def test_conditions_and_counterexamples_change_by_horizon_and_era():
 v=view(fixture());t=v['tables']['20']['all'];a=t['pre']['groups'];b=t['post']['groups']
 assert(a['first_up']['eligible'],a['first_up']['up'],a['first_up']['down'])==(25,7,18)
 assert(a['first_not_up']['eligible'],a['first_not_up']['up'],a['first_not_up']['down'])==(12,4,8)
 assert(b['first_up']['eligible'],b['first_up']['up'],b['first_up']['down'])==(5,3,2)
 assert(b['first_not_up']['eligible'],b['first_not_up']['up'],b['first_not_up']['down'])==(5,2,3)
 assert {x['symbol']for x in b['first_not_up']['excluded']}=={'603517','603838'}
 assert t['pre']['up_rate_difference_pp']<0 and t['post']['up_rate_difference_pp']>0
 assert v['tables']['40']['all']['pre']['up_rate_difference_pp']>0
 assert v['tables']['5']['all']['pre']['groups']['first_up']['eligible']==24
 assert next(r for r in v['rows']if r['symbol']=='603580')['follow']['5']['status']=='nontraded_or_missing_endpoint'
 assert(t['pre']['overlap_pair_count'],t['pre']['possible_pairs'])==(512,666)
 assert(t['post']['overlap_pair_count'],t['post']['possible_pairs'])==(27,45)
 assert v['tables']['40']['all']['pre']['overlap_pair_count']==666

def test_official_scope_excludes_in_window_mirror_action_and_original_mirror():
 v=view(fixture());t=v['tables']['40']['official_only']['pre'];assert sum(g['eligible']for g in t['groups'].values())==31
 ex={x['symbol']:x['reason']for g in t['groups'].values()for x in g['excluded']};assert ex['603580']=='source_not_strict_official'
 assert any(r['follow']['20']['official_only_eligible']for r in v['rows']if r['symbol']=='600360')

@pytest.mark.parametrize('bad',['digest','scope','comparison','ann','promotion','duplicate','first_date','first_invalid','short_window','nonfinite','question','horizon'])
def test_unearned_or_damaged_validation_is_rejected(bad):
 i=fixture();p=i['experience_case_audit'];r=i['test_comparison']['rows'][0]
 if bad=='digest':p['method_promotions']=1
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='comparison':r['name']='changed'
 elif bad=='ann':i['test_announcements']['verified_documents']+=1
 elif bad=='promotion':p['method_promotions']=1;p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 elif bad=='duplicate':i['test_comparison']['rows'][1]=deepcopy(r);seal(i)
 elif bad=='first_date':r['first_resume']['through']='2026-05-19';seal(i)
 elif bad=='first_invalid':r['first_resume']['status']='insufficient_history';seal(i)
 elif bad=='short_window':r['windows']['20']['from_resume_close']['through']=i['calendar'][-1];seal(i)
 elif bad=='nonfinite':r['windows']['20']['from_resume_close']['stock_pct']=None;seal(i)
 elif bad=='question':p['question_id']='different';p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 elif bad=='horizon':p['primary_horizon']=5;p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):view(i)

def test_legacy_no_audit():assert experience_case_audit({},None,None)is None
