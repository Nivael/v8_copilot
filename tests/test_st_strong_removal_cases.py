from pathlib import Path
import json
import pytest
from canonical_json import digest
from st_strong_removal_cases import strong_removal_cases_view,scope_digest

def fixture():
 x=json.loads((Path(__file__).parent/'fixtures/strong-removal-cases.json').read_text());i=x['input'];i['strong_removal_cases']['scope_digest']=scope_digest(i);seal(i);return i,x['cohort'],x['daily']
def seal(i):
 p=i['strong_removal_cases'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_positive_single_cash_does_not_overwrite_negative_cumulative_or_losses():
 i,c,d=fixture();v=strong_removal_cases_view(i,c,d)
 for r in v['rows']:
  assert float(r['single_quarter']['operating_cash'])>0>float(r['third']['operating_cash'])
  assert float(r['single_quarter']['parent_profit'])<0 and float(r['third']['parent_profit'])<0
  assert r['windows']['5']['after']['stock_pct']>0>r['full']['stock_pct']
  assert not any(r['known_at_removal'].values())
def test_correction_retains_old_values_and_uses_new_half_for_single_quarter():
 i,c,d=fixture();r=strong_removal_cases_view(i,c,d)['rows'][1];x=r['correction']
 assert x['original']['deducted_profit']=='-23856506.27' and r['half']['deducted_profit']=='-14304120.70'
 assert r['single_quarter']['deducted_profit']=='-11194144.47' and x['incorrect_q3_from_old_half']=='-1641758.90'
 assert x['delta']['parent_profit']==x['delta']['operating_cash']=='0.00'
@pytest.mark.parametrize('mutation',['old_half','cash','audit','source_page','future_date','identity','scope'])
def test_invalid_period_cash_source_or_scope_is_rejected(mutation):
 i,c,d=fixture();p=i['strong_removal_cases'];r=p['rows'][1]
 if mutation=='old_half':r['half']=r['correction']['original']
 if mutation=='cash':r['cash']['closing']='999999'
 if mutation=='audit':r['third']['audited']=True
 if mutation=='source_page':r['half']['metric_sources']['revenue']['page']=999
 if mutation=='future_date':r['third']['published_on']='2026-12-31'
 if mutation=='identity':r['symbol']='600000'
 if mutation=='scope':i['fixed_prices'][0]['close']=123
 seal(i)
 with pytest.raises(ValueError):strong_removal_cases_view(i,c,d)
def test_legacy_absence_is_not_fabricated():assert strong_removal_cases_view({},None,[])is None
