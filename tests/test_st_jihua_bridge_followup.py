from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_jihua_bridge_followup import jihua_bridge_followup

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-jihua-bridge-followup.json.gz').read_bytes()))
def test_partial_match_retains_unreconciled_residual_and_implied_boundaries():
 d=fixture();before=deepcopy(d);r=jihua_bridge_followup(d,d['test_prior']);assert d==before
 assert [x['difference']for x in r['rows']]==['40672.56','38852.53','38952.53']
 assert r['rows'][1]['difference']==r['same_control_premerge_profit']
 assert r['nonrec_bridge']['derived_minus_direct']=='-100.00'
 assert not r['full_reconciliation_verified'] and not any(x['implied_is_disclosed_h1']for x in r['rows'])
 r['rows'].clear();assert len(jihua_bridge_followup(d,d['test_prior'])['rows'])==3
 assert jihua_bridge_followup({},None)is None
@pytest.mark.parametrize('kind',['source','prior','residual','implied','closed'])
def test_resealed_changes_cannot_close_or_rewrite_differences(kind):
 d=fixture();p=d['jihua_bridge_followup']
 if kind=='source':next(s for s in d['twentysecond_period_followup']['sources']if s['announcement_id']=='1225644670')['selected_pages']['10']='changed'
 elif kind=='prior':d['test_prior'].clear()
 elif kind=='residual':p['result']['nonrec_bridge']['derived_minus_direct']='0.00'
 elif kind=='implied':p['result']['rows'][0]['implied_is_disclosed_h1']=True
 else:p['result']['full_reconciliation_verified']=True
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):jihua_bridge_followup(d,d['test_prior'])
