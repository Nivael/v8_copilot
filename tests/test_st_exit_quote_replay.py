import copy,gzip,json
from pathlib import Path
import pytest
from canonical_json import digest
from st_exit_quote_replay import exit_quote_replay,scope_digest

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/exit-quote-replay.json.gz').read_bytes()))
def seal(i):
 p=i['exit_quote_replay'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_old_bytes_expand_price_coverage_without_changing_source_inputs():
 f=fixture();old=copy.deepcopy(f);r=exit_quote_replay(f['input'],f['daily'],f['prior']);a=r['audit'];v=r['view']
 assert f==old and(a['raw_agree_companies'],a['qfq_agree_companies'],a['qfq_difference_companies'])==(150,139,11)
 assert(a['valid_responses'],a['reused_responses'],a['quote_points'],a['traded_security_days_replayed'])==(300,42,37432,18716)
 assert(a['additional_eastmoney_responses'],a['additional_eastmoney_quote_points'],a['all_channels_quote_points'])==(4,266,37698)
 assert(v['responses'],v['quote_points'],v['traded_security_days'],v['new_queries'])==(8,532,133,0)
 assert a['summaries']['all']==f['prior']['summaries']['all']and a['summaries']['20']==f['prior']['summaries']['20']
 assert a['qfq_basis_explained_companies']==11 and a['source_arithmetic_conflict_companies']==1
 assert a['before_exit_replay_answer']==f['prior']['answer']

def test_missing_endpoints_remain_null_while_short_windows_expand():
 f=fixture();r=exit_quote_replay(f['input'],f['daily'],f['prior']);a=r['audit'];rows={x['symbol']:x for x in a['rows']}
 assert rows['000016']['windows']['all']['checked_pct']is None and rows['002731']['windows']['all']['checked_pct']is None
 assert rows['000016']['windows']['after20']['checked_pct']is not None and rows['002731']['windows']['5']['checked_pct']is not None
 assert rows['002731']['windows']['20']['checked_pct']is None
 assert [a['summaries'][k]['paired']for k in ('all','before20','after20','before40','after40','20','5')]==[146,147,147,146,146,146,148]
 assert a['summaries']['5']['primary_positive']==117 and a['summaries']['after20']['primary_positive']==22
 for k in ('before20','before40'):assert a['summaries'][k]['paired_symbols']==a['summaries'][k.replace('before','after')]['paired_symbols']
 assert all(x['sign_changes']==0 for x in a['summaries'].values())

def test_delisting_not_used_to_fill_later_endpoint_and_suspension_not_backfilled():
 f=fixture();rows=exit_quote_replay(f['input'],f['daily'],f['prior'])['view']['rows'];k,c=rows
 assert(k['traded_days'],k['last_trade'],k['last_actual_close'],k['endpoint_actual_close'])==(82,'2026-09-03',2.46,None)
 assert(c['traded_days'],c['first_trade'],c['last_trade'],c['anchor_actual_close'],c['endpoint_actual_close'])==(51,'2026-07-07','2026-11-06',None,.22)
 assert len(k['reference_only_dates'])==17 and len(c['reference_only_dates'])==19
 assert k['zero_price_placeholder_dates']==c['zero_price_placeholder_dates']==['2026-09-18','2026-10-12','2026-10-16']
 assert not set(k['reference_only_dates'])&set(k['zero_price_placeholder_dates'])
 assert all('不补零'in x['windows']['all']['gap']for x in rows)

@pytest.mark.parametrize('bad',['packet','scope','hash','receipt_time','url','identity','duplicate','missing','reused','row_price','zero_volume','extra_date','provider_price','provider_trade','old_receipt','replay_time'])
def test_changed_receipt_quote_or_scope_cannot_be_certified(bad):
 f=fixture();i=f['input'];p=i['exit_quote_replay'];s=p['sources'][0]
 if bad=='packet':p['replayed_at']+='x'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='hash':s['raw_text']+=' '
 elif bad=='receipt_time':s['observed_at']='2026-11-09T00:00:00+00:00'
 elif bad=='url':s['url']='https://example.com'
 elif bad=='identity':s['symbol']='000017'
 elif bad=='duplicate':p['sources'][-1]=copy.deepcopy(s)
 elif bad=='missing':p['sources'].pop()
 elif bad=='reused':s['reused']=False
 elif bad in ('row_price','zero_volume','extra_date'):
  j=json.loads(s['raw_text']);bars=j['data']['sz000016']['day'];bars[0][2 if bad=='row_price'else 5 if bad=='zero_volume'else 0]='99'if bad=='row_price'else'0'if bad=='zero_volume'else'2026-11-06';s['raw_text']=json.dumps(j)
 elif bad=='provider_price':next(c for c in i['fixed_quote_audit']['original_prices']['companies']if c['symbol']=='000016')['rows'][0]['raw_close']=99
 elif bad=='provider_trade':next(c for c in i['fixed_quote_audit']['original_prices']['companies']if c['symbol']=='000016')['rows'][-1]['has_trade']=True
 elif bad=='old_receipt':i['sample_integrity']['price_verification']['results']['000016']['last_actual_close']=2.47
 elif bad=='replay_time':p['replayed_at']='2026-11-07T00:00:00+00:00'
 if bad not in ('packet','scope'):seal(i)
 with pytest.raises((ValueError,KeyError)):exit_quote_replay(i,f['daily'],f['prior'])

def test_other_148_rows_and_basis_explanations_exact():
 f=fixture();a=exit_quote_replay(f['input'],f['daily'],f['prior'])['audit']
 for old,new in zip(f['prior']['rows'],a['rows'],strict=True):
  if old['symbol']not in ('000016','002731'):assert new==old

def test_legacy_has_no_invented_replay():assert exit_quote_replay({},[],None)is None
