from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_initial_next_four import initial_next_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-next-four.json.gz').read_bytes()))
def seal(i):
 p=i['initial_next_four'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_four_initial_stages_keep_original_inventory_and_visual_scope():
 i=fixture();old=deepcopy(i);v=initial_next_four(i,i['test_prior'],i['test_current']);assert i==old
 assert [r['symbol']for r in v['rows']]==['000615','000669','000752','000826']
 assert v['counts']=={'before':46,'after':50,'remaining':100,'members':150,'new_companies':4,'new_files':11,'new_pages':36}
 assert sum(r['has_timely_reading_facts']for r in v['inventory'])==50
 assert sum(r['new_this_round']for r in v['inventory'])==4
 assert '仍待审核'in v['rows'][0]['risk_group']and '部分'in v['rows'][1]['risk_group']
 assert '正式'in v['rows'][2]['risk_group']and '延期'in v['rows'][3]['risk_group']
 assert v['rows'][2]['comparisons']['early20']['stock_pct']>0 and all(r['comparisons']['full']['stock_pct']<0 for r in v['rows'])
 assert v['quote_audit']['stock_endpoint_points']==12 and v['quote_audit']['index_endpoint_points_at_official_precision']==6
 assert v['visual_read']['bank_accounts_reported']['normal']==27 and '文本提取只有页码2'in v['visual_read']['extracted_text_limit']
 assert not v['method_promotions']and not v['full_membership_certification_added']

@pytest.mark.parametrize('bad',['selection','prior','current','market','identity','future','pages','printed','duplicate','visual_sha','visual_date','account_scope','machine_claim','partial','audit','formal','extension','stock','index'])
def test_resealed_packet_cannot_erase_scope_or_turn_application_into_removal(bad):
 i=fixture();p=i['initial_next_four'];s=p['sources'][0]
 if bad=='selection':p['selection'].reverse()
 elif bad=='prior':i['test_prior']['inventory'][0]['name']='changed'
 elif bad=='current':p['current_extension_digest']='bad'
 elif bad=='market':p['market_digest']='bad'
 elif bad=='identity':s['raw_item']['secCode']='000610'
 elif bad=='future':s['published_on']='2026-07-04'
 elif bad=='pages':s['selected_pages'].pop('1')
 elif bad=='printed':s['document_dated_on']='2026-01-01'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad=='visual_sha':p['visual_read']['image_sha256']='0'*64
 elif bad=='visual_date':p['visual_read']['document_dated_on']='2026-04-24'
 elif bad=='account_scope':p['visual_read']['bank_accounts_reported']['normal']=30
 elif bad in ['machine_claim','partial','audit','formal','extension']:
  aid,n,token={'machine_claim':('1225197985','2','2'),'partial':('1225251124','3','部分其他风险警示'),'audit':('1225251135','1','充分、适当的审计证据'),'formal':('1225196578','1','裁定受理'),'extension':('1225384023','2','尚未收到法院裁定受理重整申请')}[bad];s=next(s for s in p['sources']if s['announcement_id']==aid);s['selected_pages'][n]=s['selected_pages'][n].replace(token,'changed');s['page_hashes'][int(n)-1]=sha256(s['selected_pages'][n].encode()).hexdigest()
 else:
  key='sz000752'if bad=='stock'else'000985';s=next(s for s in p['cross_sources']if s['key']==key);raw=json.loads(s['text'])
  if bad=='stock':
   rows=raw['data'][key].get('qfqday')or raw['data'][key]['day'];next(r for r in rows if r[0]=='2026-11-19')[2]='99.99'
  else:next(r for r in raw['data']if r['tradeDate']=='20261119')['close']=9999
  s['text']=json.dumps(raw);s['sha256']=sha256(s['text'].encode()).hexdigest()
 seal(i)
 with pytest.raises(ValueError):initial_next_four(i,i['test_prior'],i['test_current'])

def test_absent_packet_keeps_previous_reader():assert initial_next_four({},None,None)is None
