from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_endpoint_basis_followup import basis_followup

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-endpoint-basis-followup.json.gz').read_bytes()))
def test_reconstructs_products_without_turning_differences_into_direct_matches():
 d=fixture();before=deepcopy(d);r=basis_followup(d,d['test_prior']);assert d==before
 assert len(r['rows'])==5 and sum(x['historical_trade_dates']for x in r['rows'])==424
 assert d['test_prior']['windows'][0]['summary']['verified_paired']==141
 j=next(x for x in r['rows']if x['symbol']=='603517');assert j['additive_start_rebuilt']=='10.340'and j['reconstructed_factor']=='1.6394'and j['reference']=='10.08'
 z=next(x for x in r['rows']if x['symbol']=='603869');assert z['cash_model']=='0.0237'and '不据模型吻合唯一识别'in z['boundary']
 assert r['new_raw_responses']==0 and len(r['encoded_raw_request_failures'])==5
 assert all(x['raw_match']and not x['additive_mismatch_dates']and not x['normalized_mismatch_dates']for x in r['rows'])
 r['rows'].clear();assert len(basis_followup(d,d['test_prior'])['rows'])==5
 assert basis_followup({},None)is None

@pytest.mark.parametrize('change',['prior','cash','source','market','scope','visual'])
def test_resealed_changes_cannot_silently_rewrite_prior_or_construction(change):
 d=fixture();p=d['endpoint_basis_followup']
 if change=='prior':d['test_prior']['windows'][0]['summary']['verified_paired']=146;p['prior_digest']=digest(d['test_prior'])
 elif change=='cash':p['result']['rows'][0]['cash_model']='0'
 elif change=='source':d['fixed_quote_audit']['sources'][0]['raw_text']='bad'
 elif change=='market':d['current_extension']['market_inputs']['fixed_prices'][0]['close']=0
 elif change=='scope':p['scope_digest']='bad'
 else:p['result']['visual_read'].pop()
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):basis_followup(d,d['test_prior'])
