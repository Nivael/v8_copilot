import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_seventh_four import initial_seventh_four

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-initial-seventh-four.json.gz').read_bytes()))
def run(x):return initial_seventh_four(x,x['test_prior'],x['test_current'])
def test_old_remediation_is_distinct_from_remaining_warning_and_price_path():
 r=run(fixture());assert r['counts']==dict(before=66,after=70,remaining=80,members=150,new_companies=4,new_files=10,new_pages=187)
 rows={x['symbol']:x for x in r['rows']}
 assert '收到最终处罚决定' in rows['002424']['known_at_anchor']
 assert '收到日不代替作出日' in rows['002424']['watch']
 assert '3亿元门槛' in rows['002485']['known_at_anchor']
 assert rows['002485']['comparisons']['full']['stock_pct'] < -29
 assert -17 < rows['002431']['comparisons']['full']['stock_pct'] < -16
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
@pytest.mark.parametrize('mutation',['digest','scope','prior','market','id','code','title','url','date','sha','clause','page','visual','crossquote','trade','annual_date','annual_boundary','old_threshold','guarantee'])
def test_rejects_source_date_coverage_and_repair_scope_corruption(mutation):
 x=fixture();p=x['initial_seventh_four'];s=p['sources'][0]
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
  s=next(s for s in p['sources']if s['announcement_id']=='1224888781');s['selected_pages']['3']=s['selected_pages']['3'].replace('作出行政处罚决定书之日起已满十二个月','changed');s['page_hashes'][2]=sha256(s['selected_pages']['3'].encode()).hexdigest()
 elif mutation=='page':s['selected_pages']['1']+='forged'
 elif mutation=='visual':p['visual_read']=[{'invented':True}]
 elif mutation=='crossquote':p['cross_sources'][0]['text']='{}'
 elif mutation=='trade':
  m=x['current_extension']['market_inputs'];r=next(r for r in m['fixed_prices']if r['symbol']=='002424'and r['trade_date']=='2026-07-03');r['has_trade']=False;p['market_digest']=digest(m)
 elif mutation in ['annual_date','annual_boundary']:
  s=next(s for s in p['sources']if s['announcement_id']=='1225244457')
  if mutation=='annual_date':s['document_dated_on']='2026-04-29'
  else:s['document_date_boundary']='invented'
 elif mutation in ['old_threshold','guarantee']:
  aid,n,old,new=('1218685262','2','1亿元','3亿元') if mutation=='old_threshold' else ('1225244457','92','12,408,550.00','0.00')
  s=next(s for s in p['sources']if s['announcement_id']==aid);s['selected_pages'][n]=s['selected_pages'][n].replace(old,new);s['page_hashes'][int(n)-1]=sha256(s['selected_pages'][n].encode()).hexdigest()
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_missing_packet_is_optional():assert initial_seventh_four({},None,None)is None
