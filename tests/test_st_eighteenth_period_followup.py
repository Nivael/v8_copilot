from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_eighteenth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-eighteenth-period-followup.json.gz').read_bytes()))

def test_updated_conditions_keep_source_scope_and_financial_distinctions():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert r['counts']['initial_coverage']==114
 assert r['counts']['complete_windows']==75 and r['counts']['unfinished_windows']==12
 assert r['counts']['stock_endpoint_gaps']==1 and len(r['chains'])==6
 assert len(r['financial_bridge'])==16 and len(r['phase_comparisons'])==36
 assert sum(x['quarter_basis']=='direct_and_difference_checked' for x in r['financial_bridge'])==12
 assert sum(x['quarter_basis']=='nine_month_minus_h1' for x in r['financial_bridge'])==4
 assert r['equity_basis']['parent_equity_yuan']=='-283932486.67'
 assert r['equity_basis']['total_equity_yuan']=='-327393277.84'
 cy=[x for x in r['phase_comparisons']if x['symbol']=='600525']
 assert cy[2]['anchor']=='2026-08-14' and float(cy[2]['stock_pct'])>0
 assert cy[3]['through']=='2026-08-26' and float(cy[3]['stock_pct'])<0
 assert r['method_promotions']==0 and followup_view({},None)is None

@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','signed_date','page','rehash','review','window'])
def test_resealed_packet_mutations_are_rejected(bad):
 d=fixture();p=d['eighteenth_period_followup'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=115
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad=='missing':p['sources'].pop()
 elif bad=='identity':s['symbol']='999999'
 elif bad=='date':s['published_on']='2026-11-20'
 elif bad=='signed_date':s['document_dated_on']='2026-01-01'
 elif bad in ['page','rehash']:
  s['selected_pages']['1']='changed'
  if bad=='rehash':
   from hashlib import sha256
   s['page_hashes'][0]=sha256(b'changed').hexdigest()
 elif bad=='review':p['visual_read'].pop()
 else:p['event_windows_digest']='changed'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(d,d['test_prior'])
