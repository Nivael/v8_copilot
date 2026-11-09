from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json,gzip
import pytest
from canonical_json import digest
from st_initial_three_quoteproof import three_quoteproof

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-three-quoteproof.json.gz').read_bytes()))
def seal(i):
 p=i['initial_three_quoteproof'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def view(i):return three_quoteproof(i,i['test_three'])
def test_replay_all_prices_and_unique_event_windows_without_new_acquisition():
 i=fixture();old=deepcopy(i);v=view(i);assert i==old
 assert (v['replayed_responses'],v['quote_points'],v['traded_security_days'])==(6,756,378)
 assert (v['event_records'],v['unique_company_days'],v['window_slots'],v['compared_windows'],v['unfinished_windows'])==(15,14,42,35,7)
 assert v['missing_quote_windows']==0 and v['all_quotes_agree']and v['all_windows_agree_to_2dp']and v['window_sign_changes']==0
 assert v['max_return_difference_pp']<1e-10 and v['new_quote_requests']==v['new_pdf_downloads']==0
@pytest.mark.parametrize('bad',['digest','case','scope','receipt','raw_hash','new_request','new_pdf','promote','duplicate','original_price','same_day'])
def test_changed_case_source_and_double_counting_fail(bad):
 i=fixture();p=i['initial_three_quoteproof']
 if bad=='digest':p['content_digest']='bad'
 elif bad=='case':i['test_three']['rows'][0]['title']='different'
 elif bad=='scope':i['fixed_prices'][0]['close']+=1
 elif bad=='receipt':p['receipts'][0]['sha256']='bad'
 elif bad=='raw_hash':i['fixed_quote_audit']['sources'][0]['raw_text']='changed'
 elif bad=='new_request':p['new_quote_requests']=1
 elif bad=='new_pdf':p['new_pdf_downloads']=1
 elif bad=='promote':p['method_promotions']=1
 elif bad=='duplicate':i['fixed_quote_audit']['sources'].append(i['fixed_quote_audit']['sources'][0])
 elif bad=='original_price':i['fixed_quote_audit']['original_prices']['companies'][0]['rows'][0]['qfq_close']+=1
 elif bad=='same_day':
  rows=[r for r in i['test_three']['rows']if r['symbol']=='000909'and r['published_on']=='2026-09-10'];rows[0]['observation']['windows']['5']['stock_pct']+=1;p['case_digest']=digest(i['test_three'])
 if bad!='digest':seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)
def mutate_quote(i,day,value=None,remove=False):
 s=next(s for s in i['fixed_quote_audit']['sources']if s['symbol']=='000909'and s['key']=='tencent_qfq');x=json.loads(s['raw_text']);rows=x['data']['sz000909'].get('qfqday')or x['data']['sz000909']['day'];r=next(r for r in rows if r[0]==day)
 if remove:rows.remove(r)
 else:r[2]=str(value)
 s['raw_text']=json.dumps(x);s['sha256']=sha256(s['raw_text'].encode()).hexdigest();i['initial_three_quoteproof']['receipts']=[{k:s[k]for k in('symbol','key','sha256','url','observed_at')}for s in i['fixed_quote_audit']['sources']];seal(i)
def test_real_price_disagreement_is_preserved_instead_of_forced_to_pass():
 i=fixture();mutate_quote(i,'2026-09-17',0.01);v=view(i);assert not v['all_quotes_agree']and not v['all_windows_agree_to_2dp']and v['window_sign_changes']>0;assert next(c for c in v['companies']if c['symbol']=='000909')['channels'][1]['differences']
def test_missing_quote_does_not_turn_unfinished_or_zero():
 i=fixture();mutate_quote(i,'2026-09-17',remove=True);v=view(i);assert v['missing_quote_windows']>0 and v['unfinished_windows']==7;w=next(r for r in v['observations']if r['symbol']=='000909'and r['published_on']=='2026-09-10')['windows']['5'];assert w['checked_pct']is None and w['status']=='missing_quote'
def test_no_packet_preserves_legacy():assert three_quoteproof({},None)is None
