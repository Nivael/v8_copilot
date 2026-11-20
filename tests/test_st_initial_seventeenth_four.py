from pathlib import Path
from copy import deepcopy
from hashlib import sha256
from decimal import Decimal as D
import gzip,json
import pytest
from canonical_json import digest
from st_initial_seventeenth_four import initial_seventeenth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-seventeenth-four.json.gz').read_bytes()))

def test_initial_risk_criteria_and_distinct_obligations_remain_visible():
 d=fixture();before=deepcopy(d);r=initial_seventeenth_four(d,d['test_prior'],d['test_current']);assert d==before
 assert r['counts']==dict(before=106,after=110,remaining=40,members=150,new_companies=4,new_files=19,new_pages=704)
 assert len(r['inventory'])==150 and sum(x['has_timely_reading_facts']for x in r['inventory'])==110
 assert [x['symbol']for x in r['rows']]==['600340','600365','600370','600381']
 assert '财报是保留意见，不是无法表示意见' in r['rows'][0]['known_at_anchor']
 assert '20%范围内赔偿' in r['rows'][1]['known_at_anchor']
 assert '无法表示意见' in r['rows'][2]['risk_group']
 assert '仍须正式审核' in r['intro']
 assert r['rows'][1]['comparisons']['early20']['stock_pct']>0>r['rows'][1]['comparisons']['full']['stock_pct']
 assert r['quote_audit']['stock_endpoint_points']==12 and r['quote_audit']['stock_return_windows']==8
 assert D(r['quote_audit']['stock_max_float_tail'])==D('1e-16')
 assert r['method_promotions']==0 and r['full_membership_certification_added']is False

def test_scans_preserve_empty_extraction_and_visual_scope():
 d=fixture();r=initial_seventeenth_four(d,d['test_prior'],d['test_current']);s=next(x for x in d['initial_seventeenth_four']['sources']if x['announcement_id']=='1225266132')
 assert all(t==''for t in s['selected_pages'].values())
 assert s['empty_text_pages']==s['pages']==111
 assert any(v['announcement_id']=='1225266132'and v['page']==3 for v in r['visual_read'])
 supports=r['rows'][3]['supporting'];assert any('文字提取为空不等于无内容' in x['note']for x in supports)
 assert next(x for x in supports if x['source']['announcement_id']=='1225266134')['source']['document_dated_on']=='2026-04-29'
 assert next(x for x in supports if x['source']['announcement_id']=='1225346266')['source']['document_dated_on']=='2026-06-02'

@pytest.mark.parametrize('bad',['order','prior','market','future','identity','sha','page','rehash','date','scan','visual','quote','catalog','duplicate_quote'])
def test_resealed_packet_cannot_rewrite_evidence_or_selection(bad):
 d=fixture();p=d['initial_seventeenth_four'];s=p['sources'][0]
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
 elif bad=='scan':s['empty_text_pages']=999
 elif bad=='visual':p['visual_read'].pop()
 elif bad=='quote':p['cross_sources'][0]['text']='{}'
 elif bad=='duplicate_quote':p['cross_sources'].append(deepcopy(p['cross_sources'][0]))
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_seventeenth_four(d,d['test_prior'],d['test_current'])
