import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_fifth_four import initial_fifth_four

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-initial-fifth-four.json.gz').read_bytes()))
def run(x):return initial_fifth_four(x,x['test_prior'],x['test_current'])
def test_four_cases_keep_application_audit_and_profit_distinct():
 r=run(fixture());assert r['counts']==dict(before=58,after=62,remaining=88,members=150,new_companies=4,new_files=6,new_pages=13)
 rows={x['symbol']:x for x in r['rows']}
 assert rows['002199']['comparisons']['full']['stock_pct'] < -33
 assert rows['002214']['comparisons']['full']['stock_pct'] > 6
 assert '仍在补材料' in rows['002214']['known_at_anchor']
 assert '无保留意见' in rows['002211']['known_at_anchor']
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
@pytest.mark.parametrize('mutation',['digest','scope','prior','market','id','code','title','url','date','sha','clause','page','visual','crossquote','trade'])
def test_rejects_source_date_coverage_and_repair_scope_corruption(mutation):
 x=fixture();p=x['initial_fifth_four'];s=p['sources'][0]
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
  s=next(s for s in p['sources']if s['announcement_id']=='1225403248');s['selected_pages']['1']=s['selected_pages']['1'].replace('补充材料','changed');s['page_hashes'][0]=sha256(s['selected_pages']['1'].encode()).hexdigest()
 elif mutation=='page':s['selected_pages']['1']+='forged'
 elif mutation=='visual':p['visual_read']=[{'invented':True}]
 elif mutation=='crossquote':p['cross_sources'][0]['text']='{}'
 elif mutation=='trade':
  m=x['current_extension']['market_inputs'];r=next(r for r in m['fixed_prices']if r['symbol']=='002199'and r['trade_date']=='2026-07-03');r['has_trade']=False;p['market_digest']=digest(m)
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_missing_packet_is_optional():assert initial_fifth_four({},None,None)is None
