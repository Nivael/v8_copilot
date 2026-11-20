from pathlib import Path
from copy import deepcopy
from decimal import Decimal
import gzip,json
import pytest
from canonical_json import digest
from st_market_stage_experience import market_stage_experience

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-market-stage-experience.json.gz').read_bytes()))
def test_disjoint_days_common_sample_and_reversal_do_not_become_independent_experiments():
 d=fixture();before=deepcopy(d);r=market_stage_experience(d,d['test_priors']);assert d==before
 dates=[day for s in r['stages']for day in s['daily_dates']];assert len(dates)==len(set(dates))==93
 assert r['common_verified_members']==139 and r['independent_regime_experiments']==0 and r['method_promotions']==0
 assert [s['verified_paired']for s in r['stages']]==[142,145,145,145,147]
 assert all(len(s['rows'])==150 for s in r['stages'])
 assert all(Decimal(s['st_minus_market_pp'])>0 for s in r['stages'][:3])and all(Decimal(s['st_minus_market_pp'])<0 for s in r['stages'][3:])
 assert sum(Decimal(s['common_sample']['median_pct'])>0 for s in r['stages'])==1
 assert market_stage_experience({},None)is None
@pytest.mark.parametrize('kind',['price','cross','official','prior','result'])
def test_resealed_mutations_cannot_change_sources_or_promote_descriptions(kind):
 d=fixture();p=d['market_stage_experience']
 if kind=='price':d['current_extension']['market_inputs']['fixed_prices'][0]['close']=1
 elif kind=='cross':d['endpoint_selection_audit']['sources'][0]['text']='bad'
 elif kind=='official':next(s for s in d['initial_twentyseventh_four']['cross_sources']if s['key']=='000985')['text']='bad'
 elif kind=='prior':d['test_priors'].clear()
 else:p['result']['independent_regime_experiments']=5
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):market_stage_experience(d,d['test_priors'])
