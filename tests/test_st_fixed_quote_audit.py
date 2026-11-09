import copy,json
from datetime import date,timedelta
from hashlib import sha256
import pytest
from canonical_json import digest
from st_fixed_quote_audit import fixed_quote_audit_view,scope_digest

def seal(i):
 p=i['fixed_quote_audit'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})
def fixture():
 cal=[];d=date(2026,5,6)
 while d<=date(2026,11,6):
  if d.weekday()<5:cal.append(d.isoformat())
  d+=timedelta(days=1)
 symbols=['000016','002731']+[f'001{x:03}' for x in range(148)];members=[{'symbol':s,'name':s,'trade_date':'2026-07-03'} for s in symbols];fixed=[];companies=[];sources=[]
 for s in symbols:
  active=s not in symbols[:2];rows=[{'date':d,'raw_close':10 if active else None,'qfq_close':10 if active else None,'adj_factor':1,'volume':10 if active else None,'has_trade':active} for d in cal];companies.append({'symbol':s,'name':s,'normalization_factor':1,'rows':rows});fixed.extend({'symbol':s,'trade_date':d,'close':10 if active else None,'has_trade':active} for d in cal)
  if active:
   ticker='sz'+s
   for key in ['tencent_raw','tencent_qfq']:
    raw=json.dumps({'data':{ticker:{'qt':{ticker:['name',s,s]},'day':[[d,10,10,10,10,10] for d in cal]}}});sources.append({'symbol':s,'key':key,'raw_text':raw,'sha256':sha256(raw.encode()).hexdigest(),'url':'https://example.test/quote','observed_at':'2026-11-09T00:00:00Z','reused':False})
 prior={s:{'receipt':'retained'} for s in symbols[:2]}
 i={'calendar':cal,'through':cal[-1],'members':members,'fixed_prices':fixed,'benchmarks':[],'sample_integrity':{'price_verification':{'results':prior}},'fixed_quote_audit':{'original_prices':{'companies':companies,'calendar':cal,'through':cal[-1],'source_refs':[]},'sources':sources,'prior_exit_receipts':prior,'failed_requests':[]}}
 daily=[{'date':d,'market_pct':0,'return_pct':0} for d in cal[1:]];seal(i);return i,daily

def test_complete_replay_is_not_all_150_certification():
 i,d=fixture();v=fixed_quote_audit_view(i,d);assert v['replayed_companies']==148 and v['total']==150 and v['raw_agree_companies']==148;assert v['summaries']['all']['paired']==148;assert v['summaries']['all']['unpaired']==2;assert v['summaries']['all']['checked_positive']==0

def test_qfq_difference_changes_answer_without_overwriting_raw_prices():
 i,d=fixture();s=i['fixed_quote_audit']['sources'][-1];x=json.loads(s['raw_text']);next(iter(x['data'].values()))['day'][-1][2]=12;s['raw_text']=json.dumps(x);s['sha256']=sha256(s['raw_text'].encode()).hexdigest();seal(i);old=copy.deepcopy(i);v=fixed_quote_audit_view(i,d)
 assert v['qfq_difference_companies']==1 and v['raw_agree_companies']==148 and v['summaries']['all']['sign_changes']==1
 assert '需要分别查看' in v['answer'] and i==old

def test_nontraded_common_endpoint_remains_null():
 i,d=fixture();s=i['fixed_quote_audit']['original_prices']['companies'][-1];s['rows'][-1].update(has_trade=False,volume=None,raw_close=None,qfq_close=None)
 for f in i['fixed_prices']:
  if f['symbol']==s['symbol'] and f['trade_date']==i['through']:f.update(has_trade=False,close=None)
 seal(i);v=fixed_quote_audit_view(i,d);assert v['rows'][-1]['windows']['all']['checked_pct'] is None;assert v['summaries']['all']['paired']==147;assert v['rows'][-1]['channels'][0]['extra_nontrade_dates']==[i['through']]

@pytest.mark.parametrize('bad',['bytes','identity','date','duplicate','missing','cohort','original','nan','trade','receipt','scope'])
def test_rejects_corrupted_or_unbound_evidence(bad):
 i,d=fixture();p=i['fixed_quote_audit'];s=p['sources'][0]
 if bad=='bytes':s['raw_text']+='x'
 elif bad in ('identity','date'):
  x=json.loads(s['raw_text']);b=next(iter(x['data'].values()))
  if bad=='identity':b['qt'][next(iter(b['qt']))][2]='999999'
  else:b['day'][0][0]='2026-01-01'
  s['raw_text']=json.dumps(x);s['sha256']=sha256(s['raw_text'].encode()).hexdigest()
 elif bad=='duplicate':p['sources'].append(copy.deepcopy(s))
 elif bad=='missing':p['sources'].pop()
 elif bad=='cohort':p['original_prices']['companies'].pop()
 elif bad=='original':p['original_prices']['companies'][-1]['rows'][-1]['qfq_close']=5
 elif bad=='nan':p['original_prices']['companies'][-1]['rows'][-1]['raw_close']=float('nan')
 elif bad=='trade':p['original_prices']['companies'][-1]['rows'][-1].update(has_trade=False,volume=None)
 elif bad=='receipt':p['prior_exit_receipts']=copy.deepcopy(p['prior_exit_receipts']);p['prior_exit_receipts']['000016']['receipt']='wrong'
 elif bad=='scope':i['benchmarks']=[{'changed':True}]
 if bad!='scope':seal(i)
 with pytest.raises((ValueError,TypeError)):fixed_quote_audit_view(i,d)

def test_old_snapshot_has_no_invented_certification():
 assert fixed_quote_audit_view({},[]) is None


def test_no_shared_endpoints_is_not_zero_distribution():
 i,d=fixture()
 for c in i['fixed_quote_audit']['original_prices']['companies']:
  for r in c['rows']:r.update(has_trade=False,volume=None,raw_close=None,qfq_close=None)
 for f in i['fixed_prices']:f.update(has_trade=False,close=None)
 seal(i);v=fixed_quote_audit_view(i,d);assert v['summaries']['all']['paired']==0 and v['summaries']['all']['primary_median_pct'] is None


def test_rule_before_after_summaries_use_identical_companies():
 i,d=fixture();c=i['fixed_quote_audit']['original_prices']['companies'][-1];j=i['calendar'].index('2026-07-03');target=i['calendar'][j+20]
 next(r for r in c['rows'] if r['date']==target).update(has_trade=False,volume=None,raw_close=None,qfq_close=None)
 next(f for f in i['fixed_prices'] if f['symbol']==c['symbol'] and f['trade_date']==target).update(has_trade=False,close=None)
 seal(i);v=fixed_quote_audit_view(i,d);a=v['summaries']['before20'];b=v['summaries']['after20'];assert a['paired_symbols']==b['paired_symbols'] and a['paired']==147
