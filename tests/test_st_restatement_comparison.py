from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_restatement_comparison import restatement_comparison

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-restatement-comparison.json.gz').read_bytes()))
def test_comparable_growth_common_date_and_unfinished_nontrading_windows():
 d=fixture();before=deepcopy(d);r=restatement_comparison(d,d['test_priors']);assert d==before
 assert r['growth_recalculation']['original_display_pct']=='17.68'
 assert r['growth_recalculation']['corrected_display_pct']=='28.24'
 assert r['counts']['common_disclosure_dates']==1 and r['method_promotions']==0
 for g in r['event_windows']:
  assert g['windows'][-1]['observed_days']==17
  assert g['windows'][-1]['status']!='complete'
  if g['symbol']=='002717':assert all(w['stock_pct']is None for w in g['windows'])
 r['cases'].clear();assert len(restatement_comparison(d,d['test_priors'])['cases'])==3
 assert restatement_comparison({},None)is None

@pytest.mark.parametrize('kind',['prior','source','market','result'])
def test_resealed_changes_cannot_rewrite_scope_or_conclusions(kind):
 d=fixture();p=d['restatement_comparison']
 if kind=='prior':d['test_priors'].clear()
 elif kind=='source':d['twentysixth_period_followup']['sources'][0]['title']='changed'
 elif kind=='market':d['current_extension']['market_inputs']['benchmarks'][0]['close']=1
 else:p['result']['method_promotions']=1
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):restatement_comparison(d,d['test_priors'])
