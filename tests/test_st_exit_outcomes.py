from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_exit_outcomes import exit_outcomes

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-exit-outcomes.json.gz').read_bytes()))
def test_exit_types_provider_dates_and_return_denominators_stay_separate():
 d=fixture();before=deepcopy(d);r=exit_outcomes(d,d['test_priors']);assert d==before
 assert r['counts']['warning_removed']==12 and len(r['rows'])==14
 assert [s['verified_paired']for s in r['removed_return_summary']]==[11,12]
 assert [s['positive']for s in r['removed_return_summary']]==[2,1]
 c=next(x for x in r['rows']if x['symbol']=='002731');assert c['classification']=='delisting_period_then_delisted'and c['provider_first_absent']=='2026-10-23';assert '11月13日摘牌'in c['later_reading']
 assert all(x['certified_return_pct']is None for x in c['returns']);assert not any(x['symbol']=='002717'for x in r['rows'])
 r['rows'].clear();assert len(exit_outcomes(d,d['test_priors'])['rows'])==14
 assert exit_outcomes({},None)is None
@pytest.mark.parametrize('kind',['membership','prior','classification','return','stage'])
def test_resealed_changes_cannot_make_list_absence_a_success_or_account_return(kind):
 d=fixture();p=d['exit_outcomes']
 if kind=='membership':d['current_extension']['market_inputs']['members'].pop()
 elif kind=='prior':d['test_priors']['removal_cohort']['rows'][0]['effective_on']='2026-07-03'
 elif kind=='classification':p['result']['rows'][0]['classification']='warning_removed'
 elif kind=='return':p['result']['rows'][0]['returns'][0]['certified_return_pct']='0'
 else:next(r for r in p['result']['rows']if r['symbol']=='002731')['official_effective_or_stage_date']='2026-11-13'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):exit_outcomes(d,d['test_priors'])
