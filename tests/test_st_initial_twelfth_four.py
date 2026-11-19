from pathlib import Path
import gzip,json
from copy import deepcopy
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_twelfth_four import initial_twelfth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-twelfth-four.json.gz').read_bytes()))

def test_initial_constraints_and_source_differences_remain_distinct():
 d=fixture();old=deepcopy(d);r=initial_twelfth_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']==dict(before=86,after=90,remaining=60,members=150,new_companies=4,new_files=18,new_pages=556)
 assert [x['symbol']for x in r['rows']]==['002932','600053','600079','600080']
 assert '暂不召开' in r['rows'][0]['known_at_anchor']
 assert '2023归母由盈转亏' in r['rows'][1]['known_at_anchor']
 assert '不替代处罚警示撤销' in r['rows'][2]['known_at_anchor']
 assert '重复占用' in r['rows'][3]['known_at_anchor']
 assert r['quote_audit']['stock_endpoint_points']==9 and r['quote_audit']['stock_return_windows']==6
 assert r['quote_audit']['index_endpoint_points_at_official_precision']==6
 assert len(r['quote_audit']['source_refs'])==6
 renfu=next(v for v in r['quote_audit']['stock_reviews']if v['symbol']=='600079')
 assert renfu['points'][0]['status']=='price_basis_conflict'
 assert all(v['return_pct'] is None for v in renfu['windows'])
 assert r['rows'][2]['comparisons']['full']['stock_pct']>0
 assert '15.6483' in r['rows'][2]['comparisons']['full']['gap']
 assert '15.6738' in r['rows'][2]['comparisons']['full']['gap']

@pytest.mark.parametrize('bad',['order','prior','market','future','identity','sha','page','rehash','date','visual','quote','quote_rehash','review'])
def test_resealed_packet_cannot_rewrite_evidence_or_selection(bad):
 d=fixture();p=d['initial_twelfth_four'];s=p['sources'][0]
 if bad=='order':p['selection'].reverse()
 elif bad=='prior':d['test_prior']['inventory'][0]['name']='changed'
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='future':s['published_on']='2026-07-04'
 elif bad=='identity':s['symbol']='999999'
 elif bad=='sha':s['sha256']='changed'
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='date':next(x for x in p['sources']if x['announcement_id']=='1225397705')['document_dated_on']='2026-04-23'
 elif bad=='visual':p['visual_read'].pop()
 elif bad=='quote':p['cross_sources'].pop()
 elif bad=='quote_rehash':
  q=next(q for q in p['cross_sources']if q['key']=='sh600079')
  q['text']=q['text'].replace('17.290','17.291');q['sha256']=sha256(q['text'].encode()).hexdigest()
 elif bad=='review':p['endpoint_review_digest']='changed'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_twelfth_four(d,d['test_prior'],d['test_current'])

def test_scan_and_confirmed_dates_preserve_original_evidence():
 d=fixture();sources={s['announcement_id']:s for s in d['initial_twelfth_four']['sources']}
 assert sources['1225050666']['selected_pages']['2']==''
 assert sources['1225250289']['selected_pages']['2']==''
 assert sources['1225397705']['document_dated_on']=='2026-06-30'
 assert sources['1225397705']['visual_date_proof']['render_sha256']
 assert sources['1225397705']['selected_pages']['1'].find('6月29日')>=0

def test_absent_packet_preserves_previous_reader():assert initial_twelfth_four({},None,None)is None
