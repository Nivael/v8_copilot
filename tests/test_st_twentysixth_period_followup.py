from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_twentysixth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-twentysixth-period-followup.json.gz').read_bytes()))
def test_verified_facts_keep_cash_scope_and_uncertified_windows_separate():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert len(r['chains'])==6 and len(r['financial_bridge'])==16
 windows=[w for g in r['event_windows']for w in g['windows']]
 assert len(windows)==84 and sum(w['status']=='unfinished'for w in windows)==12
 conflicts=[w for w in windows if w['stock_quote_check']=='price_basis_or_precision_difference']
 assert len(conflicts)==3 and all(w['stock_pct']is None and w['primary_stock_pct']is not None for w in conflicts)
 assert sum(w['stock_quote_check']=='matched'for w in windows)==80
 assert sum(w['stock_quote_check']=='not_calculable'for w in windows)==1
 assert '母公司单独' in r['chains'][-1]['changed']
 cash=next(x for x in r['financial_bridge']if x['symbol']=='603828'and x['metric']=='operating_cash')
 assert cash['reported_quarter_yuan']is None and cash['quarter_yuan']=='-59965301.11'
 assert r['method_promotions']==0 and r['counts']['initial_coverage']==146
 assert followup_view({},None)is None

@pytest.mark.parametrize('change',['source','page','visual','market','prior','windows','quote','cash'])
def test_resealed_changes_cannot_override_verified_scope(change):
 d=fixture();p=d['twentysixth_period_followup']
 if change=='source':p['sources'][0]['sha256']='bad'
 elif change=='page':p['sources'][0]['selected_pages']['1']='bad'
 elif change=='visual':p['visual_read'].pop()
 elif change=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif change=='prior':d['test_prior']['counts']['after']=150
 elif change=='windows':p['event_windows_digest']='bad'
 elif change=='quote':p['quote_reviews'][0]['cross_return_pct']='0'
 else:p['cashflow_components'].append({'bad':True})
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(d,d['test_prior'])
