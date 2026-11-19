from pathlib import Path
from copy import deepcopy
import gzip,json
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_four import initial_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-four.json.gz').read_bytes()))
def seal(i):
 p=i['initial_four'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_coverage_order_and_distinct_risks_keep_history_and_common_windows():
 i=fixture();before=deepcopy(i);v=initial_four(i,i['test_prior'],i['test_current']);assert i==before
 assert [r['symbol']for r in v['rows']]==['000056','000488','000609','000610']
 assert v['counts']=={'before':42,'after':46,'remaining':104,'members':150,'new_companies':4,'new_files':7,'new_pages':32}
 assert sum(r['new_this_round']for r in v['inventory'])==4
 assert not v['method_promotions']and not v['full_membership_certification_added']
 assert all(r['comparisons']['full']['days']==93 and r['comparisons']['early20']['days']==20 for r in v['rows'])
 assert v['rows'][3]['comparisons']['full']['stock_pct']>0
 assert all(r['comparisons']['full']['stock_pct']<0 for r in v['rows'][:3])
 assert len(v['rows'][1]['supporting'])==3 and 'B股200488'in v['rows'][1]['supporting'][2]['note']
 assert v['quote_audit']['stock_endpoint_points']==12
 assert v['quote_audit']['index_endpoint_points_at_official_precision']==6
 assert len(v['quote_audit']['unrounded_index_differences'])==6

@pytest.mark.parametrize('bad',['selection','prior','current','market','identity','future','page','opinion','remediation','B_scope','printed_date','duplicate','cross_scope','stock_crossquote','index_crossquote'])
def test_resealed_packet_cannot_change_sample_scope_or_contemporaneous_evidence(bad):
 i=fixture();p=i['initial_four'];s=p['sources'][0]
 if bad=='selection':p['selection'].reverse()
 elif bad=='prior':i['test_prior']['inventory'][0]['name']='changed'
 elif bad=='current':p['current_extension_digest']='bad'
 elif bad=='market':i['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='identity':s['raw_item']['secCode']='000488'
 elif bad=='future':s['published_on']='2026-07-04'
 elif bad=='page':s['selected_pages'].pop('2')
 elif bad in ['opinion','remediation','B_scope']:
  aid,page,token,replacement={'opinion':('1225173882','2','无法表示意见','无保留意见'),'remediation':('1225058546','7','内部控制缺陷已经整改','内部控制缺陷未整改'),'B_scope':('1225282465','1','B股股票','A股股票')}[bad]
  s=next(s for s in p['sources']if s['announcement_id']==aid);s['selected_pages'][page]=s['selected_pages'][page].replace(token,replacement);s['page_hashes'][int(page)-1]=sha256(s['selected_pages'][page].encode()).hexdigest()
 elif bad=='printed_date':s['document_dated_on']='2026-04-23'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad=='cross_scope':p['cross_sources'].pop()
 elif bad=='stock_crossquote':
  src=next(s for s in p['cross_sources']if s['key']=='sz000610');raw=json.loads(src['text']);block=raw['data']['sz000610'];rs=block.get('qfqday')or block['day'];next(r for r in rs if r[0]=='2026-11-19')[2]='99.990';src['text']=json.dumps(raw);src['sha256']=sha256(src['text'].encode()).hexdigest()
 elif bad=='index_crossquote':
  src=next(s for s in p['cross_sources']if s['key']=='000985');raw=json.loads(src['text']);next(r for r in raw['data']if r['tradeDate']=='20260703')['close']=9999;src['text']=json.dumps(raw);src['sha256']=sha256(src['text'].encode()).hexdigest()
 seal(i)
 with pytest.raises(ValueError):initial_four(i,i['test_prior'],i['test_current'])

def test_absent_supplement_keeps_old_reader():assert initial_four({},None,None)is None
