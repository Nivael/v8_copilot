from pathlib import Path
import gzip,json
from copy import deepcopy
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_thirteenth_four import initial_thirteenth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-thirteenth-four.json.gz').read_bytes()))

def test_distinct_conditions_and_contemporaneous_repairs_remain_separate():
 d=fixture();old=deepcopy(d);r=initial_thirteenth_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']==dict(before=90,after=94,remaining=56,members=150,new_companies=4,new_files=18,new_pages=390)
 assert [x['symbol']for x in r['rows']]==['600082','600084','600107','600119']
 assert '处罚警示仍有独立门槛' in r['intro']
 assert '无法确认整改有效' in r['rows'][2]['known_at_anchor']
 assert '无生效判决' in r['rows'][3]['known_at_anchor']
 assert all(x['comparisons']['full']['stock_pct']<0 for x in r['rows'])
 assert r['quote_audit']['stock_endpoint_points']==12 and r['quote_audit']['stock_return_windows']==8
 assert r['quote_audit']['index_endpoint_points_at_official_precision']==6
 assert sum(x['has_timely_reading_facts']for x in r['inventory'])==94

@pytest.mark.parametrize('bad',['order','prior','market','future','identity','sha','page','rehash','date','visual','quote'])
def test_resealed_packet_cannot_rewrite_evidence_or_selection(bad):
 d=fixture();p=d['initial_thirteenth_four'];s=p['sources'][0]
 if bad=='order':p['selection'].reverse()
 elif bad=='prior':d['test_prior']['inventory'][0]['name']='changed'
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='future':s['published_on']='2026-07-04'
 elif bad=='identity':s['symbol']='999999'
 elif bad=='sha':s['sha256']='changed'
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='date':next(x for x in p['sources']if x['announcement_id']=='1225197559')['document_dated_on']='2026-04-27'
 elif bad=='visual':p['visual_read'].pop()
 elif bad=='quote':p['cross_sources'].pop()
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_thirteenth_four(d,d['test_prior'],d['test_current'])

def test_scan_pages_remain_empty_and_signature_does_not_replace_publication():
 d=fixture();ss={s['announcement_id']:s for s in d['initial_thirteenth_four']['sources']}
 assert ss['1225197393']['selected_pages']['2']==''
 assert ss['1225197559']['document_dated_on']=='2026-04-23'
 assert ss['1225197559']['published_on']=='2026-04-27'
 assert ss['1225197559']['document_date_page']==4
 assert len(d['initial_thirteenth_four']['visual_read'])==17

def test_absent_packet_preserves_previous_reader():assert initial_thirteenth_four({},None,None)is None
