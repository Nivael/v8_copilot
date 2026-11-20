from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_lingnan_exit_followup import lingnan_followup

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-lingnan-exit-followup.json.gz').read_bytes()))
def test_later_restatements_do_not_become_final_exit_or_latest_cash_collection():
 d=fixture();before=deepcopy(d);r=lingnan_followup(d,d['test_prior']);assert d==before
 assert not r['final_decision_verified']and not r['delisting_date_verified']and r['method_promotions']==0
 assert r['trigger']['rows']==r['trigger']['below_1_count']==20
 assert r['counts']['materialized_pages']==61 and r['counts']['new_evidence_documents']==4 and r['counts']['reused_evidence_documents']==1
 assert r['timeline'][1]['date']=='2026-10-16'and r['timeline'][1]['published_on']=='2026-10-17'
 assert r['quarter']['operating_cash']['quarter']is None and r['quarter']['parent_equity']=='-1761033884.07'
 assert r['corrections'][2]['after']=='-1297384272.45'and r['quarter']['prior_year_parent_equity_restated']=='-1349766328.01'
 assert any('2025年8月25日'in b for b in r['boundaries'])
 r['timeline'].clear();assert len(lingnan_followup(d,d['test_prior'])['timeline'])==5
 assert lingnan_followup({},None)is None

@pytest.mark.parametrize('change',['source','page','visual','price','catalog','prior','final','cash'])
def test_resealed_changes_cannot_claim_exit_or_override_historical_scope(change):
 d=fixture();p=d['lingnan_exit_followup']
 if change=='source':p['sources'][0]['announcement_date']='2026-11-20'
 elif change=='page':p['sources'][0]['texts'][0]='bad'
 elif change=='visual':p['visual_read'].pop()
 elif change=='price':next(c for c in d['fixed_quote_audit']['original_prices']['companies']if c['symbol']=='002717')['rows'][0]['raw_close']=0
 elif change=='catalog':d['endpoint_reasons']['catalog']['rows'].pop()
 elif change=='prior':d['test_prior']['through']='2026-11-20';p['prior_digest']=digest(d['test_prior'])
 elif change=='final':p['result']['final_decision_verified']=True
 else:p['result']['quarter']['operating_cash']['quarter']='0'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):lingnan_followup(d,d['test_prior'])
