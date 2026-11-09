import json,gzip
from pathlib import Path
from copy import deepcopy
import pytest
from canonical_json import digest
from st_disclosure_chains import disclosure_chain_view,scope_digest,ann_digest

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/disclosure-chains.json.gz').read_bytes()))
def view(i):return disclosure_chain_view(i,i['test_ann'])
def seal(i):
 p=i['disclosure_chains'];p['scope_digest']=scope_digest(i);p['announcement_digest']=ann_digest(i['test_ann']);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_complementary_facts_survive_without_duplicate_same_day_observation():
 i=fixture();before=deepcopy(i);v=view(i);assert i==before
 assert tuple(v[k]for k in ('selected_company_chains','selected_fact_records','selected_source_documents','selected_disclosure_days','same_day_extra_fact_records','new_downloads','method_promotions'))==(3,12,13,11,1,0,0)
 cases={c['symbol']:c for c in v['cases']};wl=cases['002667'];b=next(b for b in wl['batches']if b['published_on']=='2026-10-12')
 assert len(b['nodes'])==2 and len({n['event']['source']['sha256']for n in b['nodes']})==2
 assert b['observation']['windows']['5']['stock_pct']==pytest.approx(-5.120852109791086)
 assert b['observation']['windows']['20']['stock_pct']is None
 later=wl['nodes'][-1];assert later['relation']=='later_related_control'and later['event']['occurred_on']=='2026-11-04'and later['event']['published_on']=='2026-11-06'
 assert cases['600491']['overlap']['20']['overlap_pair_count']==1
 assert cases['603398']['nodes'][1]['occurred_label']=='一拍截止日'
 assert cases['603398']['nodes'][2]['occurred_label']=='二拍截止日'
 assert all(n['event']['entity_scope']=='subsidiary'for n in cases['603398']['nodes'])

def test_completion_proof_not_moved_back_to_result_or_exact_unknown_date():
 v=view(fixture());ly=next(c for c in v['cases']if c['symbol']=='600491');result=ly['nodes'][-2];done=ly['nodes'][-1]
 assert len({s['sha256']for s in result['sources']})==2
 assert result['event']['published_on']=='2026-08-28'and result['event']['occurred_on']=='2026-08-26'and result['occurred_label']=='要约期满日'
 assert done['event']['published_on']=='2026-09-02'and done['event'].get('occurred_on')is None
 assert any('将于近日办理'in q['quote']for q in v['excerpts'])and any('清算过户手续已办理完毕'in q['quote']for q in v['excerpts'])

@pytest.mark.parametrize('bad',['digest','scope','subject','duplicate','same_day_conflict','source_sha','stage','order','excerpt','promote','corpus'])
def test_invalid_relation_or_source_not_published(bad):
 i=fixture();p=i['disclosure_chains'];e=next(e for e in i['test_ann']['verified_events']if e['id']=='tungsten_wl_offercompleted')
 if bad=='digest':p['cases'][0]['answer']='changed'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='subject':p['cases'][0]['nodes'][0]['event_id']='asset_auction'
 elif bad=='duplicate':p['cases'][0]['nodes'][2]=deepcopy(p['cases'][0]['nodes'][1])
 elif bad=='same_day_conflict':e['observation']['windows']['5']['stock_pct']=1
 elif bad=='source_sha':e['source']['sha256']='0'*64
 elif bad=='stage':p['cases'][0]['nodes'][-1]['relation']='same_tender_already_controlled'
 elif bad=='order':p['cases'][0]['nodes'].reverse()
 elif bad=='excerpt':p['excerpts'][0]['quote']='办理中'
 elif bad=='promote':p['method_promotions']=1
 elif bad=='corpus':i['test_ann']['raw_fact_records']+=1
 if bad not in ('digest','scope','corpus'):seal(i)
 with pytest.raises((ValueError,KeyError)):view(i)

def test_legacy_no_unearned_relations():assert disclosure_chain_view({},None)is None
