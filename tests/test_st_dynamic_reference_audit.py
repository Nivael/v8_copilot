import copy,json,gzip
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_dynamic_reference_audit import dynamic_reference_audit,scope_digest

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/dynamic-reference-audit.json.gz').read_bytes()))
def seal(i):
 p=i['dynamic_reference_audit'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_dynamic_scope_includes_47_prior_exits_and_six_entrants():
 f=fixture();old=copy.deepcopy(f);v=dynamic_reference_audit(f['input'],f['daily'])
 assert f==old and(v['companies'],v['pre_rule_only_companies'],v['days'])==(203,47,125)
 assert(v['trading_observations'],v['suspended_observations'])==(19009,460)
 assert(v['valid_responses'],v['new_responses'],v['reused_responses'],v['provider_cache_responses'])==(406,104,302,378)
 assert len(v['entrants'])==6 and all(r['member_price_match']for r in v['entrants'])
 z=next(r for r in v['entrants']if r['symbol']=='000972');assert z['first_member']=='2026-11-04'and z['member_days']==3 and z['prior_member_days']==36
 assert v['daily_sign_changes']==0 and not any(w['direction_changed']for w in v['windows'])
 assert v['max_daily_difference_pp']==pytest.approx(.002644800705807082)and v['stock_rate_difference_observations']==676

def test_parallel_line_does_not_replace_reference_or_claim_same_construction():
 f=fixture();v=dynamic_reference_audit(f['input'],f['daily']);w=next(w for w in v['windows']if w['key']=='all'and w['side']=='after')
 assert w['primary_change_pct']==pytest.approx(-10.926321658559711)and w['parallel_change_pct']==pytest.approx(-10.926011143744951)
 assert w['primary_correlation']==pytest.approx(.5489671076995779)
 assert len(v['daily'])==125 and all(d['member_count']==d['observed_count']+d['suspended_count']for d in v['daily'])
 assert v['stock_rate_differences'][0]['symbol']=='002592'and v['stock_rate_differences'][0]['difference_pp']>.13

def test_empty_series_only_because_entire_membership_period_suspended():
 v=dynamic_reference_audit(fixture()['input'],fixture()['daily']);assert v['empty_series']==[{'symbol':'000638','name':'*ST万方','member_days':20,'all_member_days_suspended':True}]

def test_resume_reference_uses_old_independent_close_minus_change_not_invented_prior_day():
 f=fixture();v=dynamic_reference_audit(f['input'],f['daily']);r=v['resume_references'];assert len(r)==1 and r[0]['reference']=='4.35'and r[0]['date']=='2026-07-07'and r[0]['previous_actual_date_verified']is False
 assert len(v['lookback_failures'])==2 and all(r['status']==501 for r in v['lookback_failures'])

@pytest.mark.parametrize('bad',['packet','scope','duplicate','missing','metadata','sha','identity','quote_date','raw','trade','reference','resume_identity','resume_amount','contributor','membership','suspension','empty_active'])
def test_source_scope_or_contribution_conflict_is_not_certified(bad):
 f=fixture();i=f['input'];p=i['dynamic_reference_audit'];s=p['sources'][0]
 if bad=='packet':p['through']='2026-11-05'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='duplicate':p['sources'][-1]=copy.deepcopy(s)
 elif bad=='missing':p['sources'].pop()
 elif bad=='metadata':s['observed_at']=''
 elif bad=='sha':s['raw_text']+=' '
 elif bad=='identity':s['symbol']='001111'
 elif bad=='quote_date':
  s=next(s for s in p['sources']if s['symbol']=='000793'and s['key']=='tencent_raw');j=json.loads(s['raw_text']);j['data']['sz000793']['day'][0][0]='2024-01-01';s['raw_text']=json.dumps(j);s['sha256']=sha256(s['raw_text'].encode()).hexdigest()
 elif bad in ('raw','trade','reference'):
  c=next(c for c in p['original_prices']['companies']if c['symbol']=='000793');r=next(r for r in c['rows']if r['date']=='2026-07-06');r[{'raw':'raw_close','trade':'has_trade','reference':'pre_close'}[bad]]=False if bad=='trade'else 99
 elif bad=='resume_identity':p['resume_reference']['source']['key']='eastmoney_qfq'
 elif bad=='resume_amount':p['resume_reference']['reference']='4.36'
 elif bad=='contributor':f['daily'][0]['observed_count']-=1
 elif bad=='membership':i['members']=[r for r in i['members']if not(r['symbol']=='000793'and r['trade_date']=='2026-07-06')]
 elif bad=='suspension':next(r for r in i['activities']if r['symbol']=='000793'and r['trade_date']=='2026-07-06')['suspension_status']='suspended'
 elif bad=='empty_active':next(r for r in i['activities']if r['symbol']=='000638')['suspension_status']='trading'
 if bad not in ('packet','scope'):seal(i)
 with pytest.raises((ValueError,KeyError)):dynamic_reference_audit(i,f['daily'])

def test_parallel_direction_change_revises_answer_instead_of_always_claiming_agreement():
 f=fixture();i=f['input'];s=next(s for s in i['dynamic_reference_audit']['sources']if s['symbol']=='000793'and s['key']=='tencent_qfq');j=json.loads(s['raw_text']);b=j['data']['sz000793'];bars=b.get('qfqday')or b['day'];next(r for r in bars if r[0]=='2026-07-06')[2]='9999';s['raw_text']=json.dumps(j);s['sha256']=sha256(s['raw_text'].encode()).hexdigest();seal(i);v=dynamic_reference_audit(i,f['daily']);assert v['daily_sign_changes']>0 and '出现涨跌方向差异'in v['answer']and '均未改变'not in v['answer']

def test_legacy_does_not_invent_audit():assert dynamic_reference_audit({},[])is None
