from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_endpoint_reasons import endpoint_reasons

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-endpoint-reasons.json.gz').read_bytes()))
def seal(i):
 p=i['endpoint_reasons'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def view(i):return endpoint_reasons(i,i['test_current'],i['test_integrity'],i['test_halts'])
def test_two_windows_keep_four_company_paths_without_imputation_or_new_evidence_claims():
 i=fixture();old=deepcopy(i);v=view(i);assert i==old
 assert [(w['covered'],w['missing'],w['total'])for w in v['windows']]==[(146,4,150),(147,3,150)]
 full,recent=v['windows'];long=next(r for r in full['rows']if r['symbol']=='600491');now=next(r for r in recent['rows']if r['symbol']=='600491');assert long['return_pct']is None and long['anchor']['traded_qfq_close']is None and now['return_pct']is not None
 ling=next(r for r in recent['rows']if r['symbol']=='002717');assert ling['anchor']['traded_qfq_close']is None and ling['anchor']['reference_qfq_close']is not None
 assert '最终决定和摘牌日未核'in ling['endpoint']['meaning']
 assert next(r for r in recent['rows']if r['symbol']=='002731')['anchor']['traded_qfq_close']is not None
 assert v['counts']=={'new_primary_documents':0,'reused_primary_documents':9,'reused_primary_pages':24,'rechecked_rendered_pages':10,'new_price_points':0}
 assert v['directory_review']['record_count']==34 and not v['directory_review']['matched_final_titles']
 assert not v['method_promotions']

@pytest.mark.parametrize('bad',['digest','current','integrity','halts','market','source_identity','source_title','source_time','pages','duplicate','cash','notice','resume','catalog','catalog_identity','fake_trade','halt_volume'])
def test_resealed_packet_does_not_turn_missing_prices_or_notices_into_exits(bad):
 i=fixture();p=i['endpoint_reasons'];s=p['sources'][0]
 if bad=='digest':p['content_digest']='bad'
 elif bad in ['current','integrity','halts','market']:p[{'current':'current_digest','integrity':'integrity_digest','halts':'halt_digest','market':'market_digest'}[bad]]='bad'
 elif bad=='source_identity':s['symbol']='000615'
 elif bad=='source_title':s['title']='changed'
 elif bad=='source_time':s['original_observed_at']='2026-11-20T00:00:00Z'
 elif bad=='pages':s['selected_pages'].pop('1')
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad in ['cash','notice','resume']:
  aid,n,token={'cash':('1225605494','2','已完成交收'),'notice':('1225609701','1','拟决定'),'resume':('1225417943','1','2026/7/10')}[bad];s=next(s for s in p['sources']if s['announcement_id']==aid);s['selected_pages'][n]=s['selected_pages'][n].replace(token,'changed');s['page_hashes'][int(n)-1]=sha256(s['selected_pages'][n].encode()).hexdigest()
 elif bad=='catalog':p['catalog']['rows'].pop()
 elif bad=='catalog_identity':p['catalog']['rows'][0]['raw_item']['secCode']='000016'
 elif bad=='fake_trade':
  r=next(r for r in i['current_extension']['market_inputs']['fixed_prices']if r['symbol']=='600491'and r['trade_date']=='2026-07-03');r['has_trade']=True;p['market_digest']=digest(i['current_extension']['market_inputs'])
 elif bad=='halt_volume':
  r=next(r for r in i['current_extension']['market_inputs']['activities']if r['symbol']=='002717'and r['trade_date']=='2026-11-19');r['volume']=1;p['market_digest']=digest(i['current_extension']['market_inputs'])
 if bad!='digest':seal(i)
 with pytest.raises(ValueError):view(i)

def test_absence_keeps_legacy_view():assert endpoint_reasons({},None,None,None)is None
