from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_initial_fifteenth_four import initial_fifteenth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-fifteenth-four.json.gz').read_bytes()))

def test_four_initial_cases_and_nontraded_window_stay_distinct():
 d=fixture();before=deepcopy(d);r=initial_fifteenth_four(d,d['test_prior'],d['test_current']);assert d==before
 assert r['counts']==dict(before=98,after=102,remaining=48,members=150,new_companies=4,new_files=28,new_pages=601)
 assert len(r['inventory'])==150 and sum(x['has_timely_reading_facts']for x in r['inventory'])==102
 assert [x['symbol'] for x in r['rows']]==['600187','600238','600239','600243']
 assert r['rows'][1]['comparisons']['early20']['stock_pct'] is None
 assert r['rows'][1]['comparisons']['full']['stock_pct'] is not None
 assert '万元改元' in r['rows'][0]['watch']
 assert '补材料' in r['rows'][1]['known_at_anchor']
 assert '19.6亿元差额补足义务到期尚未履行' in r['rows'][2]['known_at_anchor']
 assert '不当新增利润或现金' in r['rows'][3]['known_at_anchor']
 assert r['quote_audit']['stock_endpoint_points']==11 and r['quote_audit']['stock_return_windows']==7
 assert r['quote_audit']['index_endpoint_points_at_official_precision']==6
 assert len(r['quote_audit']['source_refs'])==6
 assert '4.14元仅是停牌参考值' in r['quote_audit']['review_note']
 assert r['method_promotions']==0 and r['full_membership_certification_added'] is False

@pytest.mark.parametrize('bad',['order','prior','market','future','identity','sha','page','rehash','date','visual','quote','catalog'])
def test_resealed_packet_cannot_rewrite_evidence_or_selection(bad):
 d=fixture();p=d['initial_fifteenth_four'];s=p['sources'][0]
 if bad=='catalog':p['catalog_scope']['current_complete']=False
 elif bad=='order':p['selection'].reverse()
 elif bad=='prior':d['test_prior']['inventory'][0]['name']='changed'
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='future':s['published_on']='2026-07-04'
 elif bad=='identity':s['symbol']='999999'
 elif bad=='sha':s['sha256']='changed'
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='date':s['document_dated_on']='2026-01-01'
 elif bad=='visual':p['visual_read'].pop()
 elif bad=='quote':p['cross_sources'][0]['text']='{}'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_fifteenth_four(d,d['test_prior'],d['test_current'])
