from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_sixteenth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-sixteenth-period-followup.json.gz').read_bytes()))

def test_new_fulfillment_does_not_erase_distinct_remaining_obligations():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert r['counts']['initial_coverage']==106 and r['counts']['complete_windows']==88
 assert r['counts']['unfinished_windows']==14 and r['counts']['stock_endpoint_gaps']==0
 assert len(r['chains'])==13 and len(r['financial_bridge'])==16
 text=' '.join(c['changed']+' '+c['open']for c in r['chains'])
 for token in ['已清偿','两宗恢复执行','权益性交易','资本公积','签章后生效','两份重整计划均获法院批准','不能写成清算注销完成']:
  assert token in text
 assert r['method_promotions']==0

def test_original_penny_differences_are_preserved_as_differences():
 d=fixture();r=followup_view(d,d['test_prior']);f=r['financial_bridge']
 assert [(x['symbol'],x['metric'],x['quarter_yuan'],x['reported_quarter_yuan'],x['quarter_difference_yuan'])for x in f if x['quarter_basis']=='reported_and_difference_conflict']==[('600302','recurring_profit','-33144458.54','-33144458.53','-0.01'),('600337','operating_cash','-3534710.26','-3534710.25','-0.01')]
 assert sum(x['quarter_basis']=='direct_and_difference_checked'for x in f)==11
 assert sum(x['quarter_basis']=='nine_month_minus_h1'for x in f)==3
 assert sum(x['reported_h1_yoy_marker']=='不适用'for x in f)==10

def test_phase_comparison_retains_counterexample_to_simple_signing_story():
 d=fixture();r=followup_view(d,d['test_prior']);m=[x for x in r['phase_comparisons']if x['symbol']=='600337']
 assert len(r['phase_comparisons'])==28
 assert float(m[1]['stock_pct'])<0<float(m[1]['st_pct'])
 assert m[2]['through']=='2026-08-27'and float(m[2]['stock_pct'])>0
 assert m[4]['anchor']=='2026-09-23'and float(m[4]['stock_pct'])>0>float(m[4]['market_pct'])

@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','signed_date','page','rehash','review','window'])
def test_resealed_changes_are_rejected(bad):
 d=fixture();p=d['sixteenth_period_followup'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=107
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
