import gzip,json,copy
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_yigou_settlement import yigou_settlement

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-yigou-settlement.json.gz').read_bytes()))
def run(x):return yigou_settlement(x,x['test_prior'])
def test_distinguishes_aggregate_profit_cash_and_specific_settlement():
 r=run(fixture());f={x['key']:x for x in r['financials']}
 assert f['nine']['values']['net']==54117
 assert f['nine']['values']['core']==-3500298
 assert f['quarter']['values']['cash']==-119265
 assert f['quarter']['cash_derived']and not f['nine']['cash_derived']
 assert f['quarter']['yi_yuan']['cash']==-1.19265
 assert all(x['values']['net']==x['values']['core']+x['values']['nonrecurring']for x in f.values())
 assert r['events'][0]['windows'][0]['through']=='2026-08-31'
 assert r['events'][1]['windows'][2]['complete']is False
 assert r['events'][1]['windows'][2]['stock_pct']is None
 assert len(r['monthly'])==5 and r['full']['days']==93
 assert r['method_promotions']==0 and not r['tracked_list_changed']
 assert r['counts']['new_quote_requests']==0
 assert len(r['scope_traps'])==3 and '另一侧审批、正式签约和分期支付' in r['specific_settlement_stage']
@pytest.mark.parametrize('mutation',['digest','prior','market','symbol','date','title','url','source_sha','source_count','reuse','page_hash','raw_text','clause','catalog','quote','volume','profit','cash','unit'])
def test_fails_closed_on_source_scope_chronology_units_and_market_changes(mutation):
 x=fixture();p=x['yigou_settlement'];s=next(s for s in p['sources']if s['announcement_id']=='1225638414')
 if mutation=='digest':p['content_digest']='bad'
 elif mutation=='prior':p['prior_digest']='bad'
 elif mutation=='market':p['market_digest']='bad'
 elif mutation=='symbol':s['symbol']='000001'
 elif mutation=='date':s['published_on']='2026-11-20'
 elif mutation=='title':s['title']='bad'
 elif mutation=='url':s['url']='https://example.org/'
 elif mutation=='source_sha':s['sha256']='0'*64
 elif mutation=='source_count':p['sources'].pop()
 elif mutation=='reuse':s['reused']=True
 elif mutation=='page_hash':s['selected_pages']['1']+='forged'
 elif mutation=='raw_text':s['text_pages']['1']+='forged'
 elif mutation=='clause':
  s=next(s for s in p['sources']if s['announcement_id']=='1225388521');s['selected_pages']['4']=s['selected_pages']['4'].replace('99.28%','99.29%');s['page_hashes'][3]=sha256(s['selected_pages']['4'].encode()).hexdigest();s['text_pages']['4']=s['text_pages']['4'].replace('99.28%','99.29%')
 elif mutation=='catalog':p['catalog']['rows'].pop()
 elif mutation=='quote':p['cross_sources'][0]['text']='{}'
 elif mutation=='volume':
  x['current_extension']['market_inputs']['fixed_prices'][0]['has_trade']=False
 elif mutation in ['profit','cash','unit']:
  a,b={'profit':('54,117','54,118'),'cash':('1,501,243','1,501,244'),'unit':('单位：千元','单位：万元')}[mutation]
  s['text_pages']['1']=s['text_pages']['1'].replace(a,b);s['selected_pages']['1']=s['selected_pages']['1'].replace(a.replace('：',':'),b.replace('：',':'));s['page_hashes'][0]=sha256(s['selected_pages']['1'].encode()).hexdigest()
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_absence_is_optional():assert yigou_settlement({},None)is None
