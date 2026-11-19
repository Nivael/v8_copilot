import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_initial_fourth_four import initial_fourth_four

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-initial-fourth-four.json.gz').read_bytes()))
def run(x):return initial_fourth_four(x,x['test_prior'],x['test_current'])
def test_four_source_bound_cases_keep_risk_stage_and_common_window_distinct():
 r=run(fixture());assert r['counts']==dict(before=54,after=58,remaining=92,members=150,new_companies=4,new_files=11,new_pages=50)
 assert len(r['inventory'])==150 and sum(s['has_timely_reading_facts']for s in r['inventory'])==58
 rows={r['symbol']:r for r in r['rows']}
 assert rows['002122']['comparisons']['full']['stock_pct']>5
 assert rows['002168']['comparisons']['full']['stock_pct']<-26
 assert rows['002055']['comparisons']['early20']['stock_pct']<-22
 assert r['quote_audit']['stock_endpoint_points']==12 and not r['full_membership_certification_added']and r['method_promotions']==0
 assert '不是全部资金均以现金收回'in rows['002055']['known_at_anchor']
 assert '不能停留在事先告知'in rows['002122']['known_at_anchor']
 assert '5月11日起已正式撤销'in rows['002168']['known_at_anchor']
 assert '无法合理估计影响金额'in rows['002193']['known_at_anchor']
@pytest.mark.parametrize('mutation',['digest','scope','prior','market','id','code','title','url','date','sha','clause','page','scan','visual','crossquote','clock','trade'])
def test_rejects_source_date_coverage_and_repair_scope_corruption(mutation):
 x=fixture();p=x['initial_fourth_four'];s=p['sources'][0]
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
 elif mutation in ['clause','clock']:
  aid,n,token=('1225282697',3,'不代表公司正式进入重整程序')if mutation=='clause'else('1225326146',6,'收到《行政处罚决定书》之日起满12个月');s=next(s for s in p['sources']if s['announcement_id']==aid);s['selected_pages'][str(n)]=s['selected_pages'][str(n)].replace(token,'changed');s['page_hashes'][n-1]=sha256(s['selected_pages'][str(n)].encode()).hexdigest()
 elif mutation=='page':s['selected_pages']['1']+='forged'
 elif mutation=='scan':
  s=next(s for s in p['sources']if s['announcement_id']=='1225244280');s['selected_pages']['3']='invented';s['page_hashes'][2]=sha256(b'invented').hexdigest()
 elif mutation=='visual':p['visual_read'][0]['note']='all warnings removed'
 elif mutation=='crossquote':p['cross_sources'][0]['text']='{}'
 elif mutation=='trade':
  m=x['current_extension']['market_inputs'];r=next(r for r in m['fixed_prices']if r['symbol']=='002055'and r['trade_date']=='2026-07-03');r['has_trade']=False;p['market_digest']=digest(m)
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_search_highlighting_is_not_a_different_title():
 x=fixture();p=x['initial_fourth_four'];s=next(s for s in p['sources']if s['announcement_id']=='1224812570');assert '<em>'in s['raw_item']['announcementTitle'];s['raw_item']['announcementTitle']=s['title'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'});assert run(x)['counts']['after']==58
def test_missing_packet_is_optional():assert initial_fourth_four({},None,None)is None
