from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_seventeenth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-seventeenth-period-followup.json.gz').read_bytes()))

def test_changes_keep_distinct_remaining_conditions_and_source_scope():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert r['counts']['initial_coverage']==110
 assert r['counts']['complete_windows']==86 and r['counts']['unfinished_windows']==13
 assert len(r['chains'])==4 and len(r['financial_bridge'])==16
 assert len(r['phase_comparisons'])==36 and r['method_promotions']==0
 assert r['par_value_check']['consecutive_sub_one_observed_days']==3
 assert r['par_value_check']['basis']=='Tencent day unadjusted, not qfqday'
 assert sum(x['quarter_basis']=='direct_and_difference_checked' for x in r['financial_bridge'])==12
 assert sum(x['quarter_basis']=='nine_month_minus_h1' for x in r['financial_bridge'])==4
 m=next(x for x in r['financial_bridge']if x['symbol']=='600370'and x['metric']=='parent_profit')
 assert float(m['h1_yuan'])>0>float(m['quarter_yuan'])
 a=next(x for x in r['event_windows'] if x['aid']=='1225586286')
 assert float(a['windows'][0]['stock_pct'])>0>float(a['windows'][2]['stock_pct'])
 assert followup_view({},None) is None

@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','signed_date','page','rehash','review','window'])
def test_resealed_packet_mutations_are_rejected(bad):
 d=fixture();p=d['seventeenth_period_followup'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=111
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
