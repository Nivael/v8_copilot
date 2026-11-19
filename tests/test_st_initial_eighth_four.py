import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_eighth_four import initial_eighth_four

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-initial-eighth-four.json.gz').read_bytes()))
def run(x):return initial_eighth_four(x,x['test_prior'],x['test_current'])
def test_stage_audit_scope_and_opposing_price_paths_remain_distinct():
 r=run(fixture());assert r['counts']==dict(before=70,after=74,remaining=76,members=150,new_companies=4,new_files=13,new_pages=121)
 rows={s['symbol']:s for s in r['rows']}
 assert '6月18日股东会已通过' in rows['002528']['known_at_anchor']
 assert '连续两年内控无法表示意见' in rows['002630']['known_at_anchor']
 assert '6.5亿元' in rows['002634']['watch']
 assert rows['002528']['comparisons']['full']['stock_pct']>18
 assert rows['002634']['comparisons']['full']['stock_pct'] < -27
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
@pytest.mark.parametrize('kind',['digest','selection','prior','market','id','symbol','title','url','future_date','sha','page','rehash','visual','crossquote','scan_date','scan_proof','main_signature'])
def test_rejects_false_identity_dates_stage_text_and_visual_proof(kind):
 x=fixture();p=x['initial_eighth_four'];s=p['sources'][0]
 if kind=='digest':p['content_digest']='bad'
 elif kind=='selection':p['selection'][0]='000001'
 elif kind=='prior':p['prior_inventory_digest']='bad'
 elif kind=='market':p['market_digest']='bad'
 elif kind=='id':s['raw_item']['announcementId']='bad'
 elif kind=='symbol':s['symbol']='000001'
 elif kind=='title':s['title']='bad'
 elif kind=='url':s['url']='https://example.org/'
 elif kind=='future_date':s['published_on']='2026-07-04'
 elif kind=='sha':s['sha256']='bad'
 elif kind in ['page','rehash']:
  s['selected_pages']['1']+='forged'
  if kind=='rehash':s['page_hashes'][0]=sha256(s['selected_pages']['1'].encode()).hexdigest()
 elif kind=='visual':p['visual_read']=[]
 elif kind=='crossquote':p['cross_sources'][0]['text']='{}'
 elif kind in ['scan_date','scan_proof']:
  s=next(s for s in p['sources']if s['announcement_id']=='1225251557')
  if kind=='scan_date':s['document_dated_on']='2026-04-29'
  else:s['visual_date_proof']['render_sha256']='bad'
 elif kind=='main_signature':next(s for s in p['sources']if s['announcement_id']=='1225195310')['document_date_page']=8
 if kind!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_missing_packet_optional():assert initial_eighth_four({},None,None)is None
