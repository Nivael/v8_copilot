"""Guard source chronology, scanned evidence, actual sample coverage and common windows."""
import copy,gzip,json
from pathlib import Path
import pytest
from canonical_json import digest
from st_initial_third_four import initial_third_four

def fixture():
 return json.loads(gzip.decompress(Path('tests/fixtures/st-initial-third-four.json.gz').read_bytes()))
def run(x):return initial_third_four(x,x['test_prior'],x['test_current'])
def test_current_batch_retains_sample_and_closes_only_four_coverage_gaps():
 x=fixture();r=run(x)
 assert r['counts']==dict(before=50,after=54,remaining=96,members=150,new_companies=4,new_files=10,new_pages=42)
 assert len(r['inventory'])==150
 assert sum(s['has_timely_reading_facts']for s in r['inventory'])==54
 assert [s['symbol']for s in r['rows']]==['000838','000903','000911','002024']
 assert r['rows'][0]['comparisons']['early20']['stock_pct']>41
 assert r['rows'][0]['comparisons']['full']['stock_pct']<-32
 assert r['rows'][2]['comparisons']['full']['stock_pct']>0
 assert r['quote_audit']['stock_endpoint_points']==12
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
@pytest.mark.parametrize('mutation',['digest','scope','prior','market','id','code','title','url','date','sha','clause','page','scan','visual','crossquote'])
def test_rejects_changed_source_scope_dates_and_scanned_evidence(mutation):
 x=fixture();p=x['initial_third_four'];s=p['sources'][0]
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
  s=next(s for s in p['sources']if s['announcement_id']=='1225388521');s['selected_pages']['4']=s['selected_pages']['4'].replace('99.28%','98%');s['page_hashes'][3]=__import__('hashlib').sha256(s['selected_pages']['4'].encode()).hexdigest()
 elif mutation=='page':s['selected_pages']['1']+='forged'
 elif mutation=='scan':
  s=next(s for s in p['sources']if s['announcement_id']=='1225212367');s['selected_pages']['2']='invented OCR';s['page_hashes'][1]=__import__('hashlib').sha256(b'invented OCR').hexdigest()
 elif mutation=='visual':p['visual_read'][0]['note']='all warnings removed'
 elif mutation=='crossquote':p['cross_sources'][0]['text']='{}'
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_absent_packet_stays_optional():assert initial_third_four({},None,None)is None
