import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_dongjing_dali_followup import followup_view

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-dongjing-dali-followup.json.gz').read_bytes()))
def run(x):return followup_view(x,x['test_prior'],x['test_current'])
def test_paths_reverse_the_short_window_impression_without_claiming_causality():
 r=run(fixture());a,b=r['rows'];assert float(a['windows'][2]['stock_pct'])>32 and float(a['windows'][1]['stock_pct'])<0;assert float(b['windows'][2]['stock_pct'])<1 and float(b['windows'][1]['stock_pct'])>0;assert a['quarter']['operating_cash']=='8762762.71' and b['quarter']['operating_cash']=='-40442161.30';assert r['counts']['initial_coverage']==62 and r['method_promotions']==0
@pytest.mark.parametrize('mutation',['digest','prior','market','current','source_sha','source_symbol','source_date','source_url','source_page','cash','cash_balanced','quarter','financial','known_date','old_correction','clause'])
def test_rejects_source_scope_financial_and_information_date_changes(mutation):
 x=fixture();p=x['dongjing_dali_followup'];s=p['sources'][0];d=p['financials']['002214']
 if mutation=='digest':p['content_digest']='bad'
 elif mutation=='prior':p['prior_digest']='bad'
 elif mutation=='market':p['market_digest']='bad'
 elif mutation=='current':p['current_digest']='bad'
 elif mutation=='source_sha':s['sha256']='bad'
 elif mutation=='source_symbol':s['symbol']='002214' if s['symbol']=='002199'else'002199'
 elif mutation=='source_date':s['announcement_date']='2026-07-01'
 elif mutation=='source_url':s['url']='https://example.com/'
 elif mutation=='source_page':s['selected_pages']['1']+='forged'
 elif mutation=='cash':d['cash']['change']='0'
 elif mutation=='cash_balanced':d['cash']['investing']='-22847016.36';d['cash']['financing']='93984986.70'
 elif mutation=='quarter':d['single_quarter']['operating_cash']='0'
 elif mutation=='financial':d['third']['parent_profit']='0'
 elif mutation=='known_date':d['half']['published_on']='2026-07-03'
 elif mutation=='old_correction':p['financials']['002199']['half']['deducted_profit']='-23856506.27'
 elif mutation=='clause':
  s=next(s for s in p['sources']if s['announcement_id']=='1225436048');s['selected_pages']['1']=s['selected_pages']['1'].replace('2026年7月23日','2026年7月24日');s['page_hashes'][0]=sha256(s['selected_pages']['1'].encode()).hexdigest()
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_missing_packet_is_optional():assert followup_view({},None,None)is None
