from pathlib import Path
import gzip,json
from copy import deepcopy
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_eleventh_four import initial_eleventh_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-eleventh-four.json.gz').read_bytes()))

def test_repaired_conditions_and_unresolved_approval_remain_distinct():
 d=fixture();old=deepcopy(d);r=initial_eleventh_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']==dict(before=82,after=86,remaining=64,members=150,new_companies=4,new_files=14,new_pages=179)
 assert [x['symbol']for x in r['rows']]==['002822','002856','002872','002883']
 assert '不等于已经摘帽'in r['rows'][0]['known_at_anchor']
 assert '已获交易所批准撤销'in r['rows'][2]['known_at_anchor']
 assert r['rows'][2]['comparisons']['full']['stock_pct']>0
 assert all(x['comparisons']['full']['stock_pct']<0 for x in [r['rows'][0],r['rows'][1],r['rows'][3]])
 assert r['quote_audit']['stock_endpoint_points']==12 and r['quote_audit']['stock_return_windows']==8
 assert r['quote_audit']['index_endpoint_points_at_official_precision']==6

@pytest.mark.parametrize('bad',['order','prior','market','future','identity','sha','page','rehash','date','visual','quote'])
def test_resealed_packet_cannot_rewrite_evidence_or_selection(bad):
 d=fixture();p=d['initial_eleventh_four'];s=p['sources'][0]
 if bad=='order':p['selection'].reverse()
 elif bad=='prior':d['test_prior']['inventory'][0]['name']='changed'
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='future':s['published_on']='2026-07-04'
 elif bad=='identity':s['symbol']='999999'
 elif bad=='sha':s['sha256']='changed'
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='date':next(x for x in p['sources']if x['announcement_id']=='1225155507')['document_dated_on']='2026-04-23'
 elif bad=='visual':p['visual_read'].pop()
 elif bad=='quote':p['cross_sources'].pop()
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_eleventh_four(d,d['test_prior'],d['test_current'])

def test_scan_signature_text_is_not_invented():
 d=fixture();s=next(s for s in d['initial_eleventh_four']['sources']if s['announcement_id']=='1225155507')
 assert s['selected_pages']['3']=='' and s['document_dated_on']=='2026-04-21' and s['document_date_page']==3
 assert s['visual_date_proof']['render_sha256']

def test_absent_packet_preserves_previous_reader():assert initial_eleventh_four({},None,None)is None
