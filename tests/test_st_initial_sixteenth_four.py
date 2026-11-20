from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import gzip,json
import pytest
from canonical_json import digest
from st_initial_sixteenth_four import initial_sixteenth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-sixteenth-four.json.gz').read_bytes()))

def test_initial_sources_and_reversal_comparison_preserve_boundaries():
 d=fixture();before=deepcopy(d);r=initial_sixteenth_four(d,d['test_prior'],d['test_current']);assert d==before
 assert r['counts']==dict(before=102,after=106,remaining=44,members=150,new_companies=4,new_files=24,new_pages=607)
 assert len(r['inventory'])==150 and sum(x['has_timely_reading_facts']for x in r['inventory'])==106
 assert [x['symbol']for x in r['rows']]==['600265','600289','600302','600337']
 assert all(x['comparisons']['full']['stock_pct']<0 for x in r['rows'][:3])
 assert r['rows'][3]['comparisons']['early20']['stock_pct']<0<r['rows'][3]['comparisons']['full']['stock_pct']
 assert '原件单位冲突' in r['rows'][0]['known_at_anchor']
 assert '恢复执行' in r['rows'][1]['known_at_anchor']
 assert '不能据此宣告内控有效或摘帽' in r['rows'][2]['known_at_anchor']
 assert '两主体分开' in r['rows'][3]['known_at_anchor']
 assert r['quote_audit']['stock_endpoint_points']==12 and r['quote_audit']['stock_return_windows']==8
 assert r['quote_audit']['index_endpoint_points_at_official_precision']==6
 assert len(r['visual_read'])==15
 assert r['method_promotions']==0 and r['full_membership_certification_added']is False

@pytest.mark.parametrize('bad',['order','prior','market','future','identity','sha','page','rehash','date','visual','quote','catalog','duplicate_quote'])
def test_resealed_packet_cannot_rewrite_evidence_or_selection(bad):
 d=fixture();p=d['initial_sixteenth_four'];s=p['sources'][0]
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
 elif bad=='duplicate_quote':p['cross_sources'].append(deepcopy(p['cross_sources'][0]))
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_sixteenth_four(d,d['test_prior'],d['test_current'])
