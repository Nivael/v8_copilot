import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_sixth_four import initial_sixth_four

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-initial-sixth-four.json.gz').read_bytes()))
def run(x):return initial_sixth_four(x,x['test_prior'],x['test_current'])
def test_old_remediation_is_distinct_from_remaining_warning_and_price_path():
 r=run(fixture());assert r['counts']==dict(before=62,after=66,remaining=84,members=150,new_companies=4,new_files=6,new_pages=23)
 rows={x['symbol']:x for x in r['rows']}
 assert '不把告知书当最终处罚决定' in rows['002217']['known_at_anchor']
 assert '4月22日起仍新实施' in rows['002227']['known_at_anchor']
 assert '6月12日起已正式撤销' in rows['002306']['known_at_anchor']
 assert '新增一般户冻结' in rows['002306']['known_at_anchor']
 assert rows['002306']['comparisons']['full']['stock_pct'] < -33
 assert -20 < rows['002323']['comparisons']['full']['stock_pct'] < -19
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
@pytest.mark.parametrize('mutation',['digest','scope','prior','market','id','code','title','url','date','sha','clause','page','visual','crossquote','trade'])
def test_rejects_source_date_coverage_and_repair_scope_corruption(mutation):
 x=fixture();p=x['initial_sixth_four'];s=p['sources'][0]
 if mutation=='digest':p['content_digest']='bad'
 elif mutation=='scope':p['selection'][0]='000001'
 elif mutation=='prior':p['prior_inventory_digest']='bad'
 elif mutation=='market':p['market_digest']='bad'
 elif mutation=='id':s['raw_item']['announcementId']='bad'
 elif mutation=='code':s['symbol']='000001'
 elif mutation=='title':s['title']='bad'
 elif mutation=='url':s['url']='https://example.org/'
 elif mutation=='date':s['published_on']='2026-07-04'
 elif mutation=='sha':s['sha256']='0'*64
 elif mutation=='clause':
  s=next(s for s in p['sources']if s['announcement_id']=='1225363995');s['selected_pages']['3']=s['selected_pages']['3'].replace('基本银行账户已解除冻结并新增一般银行账户冻结','changed');s['page_hashes'][2]=sha256(s['selected_pages']['3'].encode()).hexdigest()
 elif mutation=='page':s['selected_pages']['1']+='forged'
 elif mutation=='visual':p['visual_read']=[{'invented':True}]
 elif mutation=='crossquote':p['cross_sources'][0]['text']='{}'
 elif mutation=='trade':
  m=x['current_extension']['market_inputs'];r=next(r for r in m['fixed_prices']if r['symbol']=='002217'and r['trade_date']=='2026-07-03');r['has_trade']=False;p['market_digest']=digest(m)
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_missing_packet_is_optional():assert initial_sixth_four({},None,None)is None
