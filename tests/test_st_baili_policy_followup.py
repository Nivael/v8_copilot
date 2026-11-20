from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_baili_policy_followup import baili_policy_followup

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-baili-policy-followup.json.gz').read_bytes()))
def test_policy_predates_h1_and_does_not_certify_treatment_or_cash():
 d=fixture();before=deepcopy(d);r=baili_policy_followup(d,d['test_prior']);assert d==before
 assert r['verified']['h1_mentions_policy']and not r['verified']['policy_after_h1_disclosure']
 assert not r['verified']['accounting_treatment_certified']and not r['verified']['cash_payment_proven']
 assert r['timeline'][2]['date']=='2026-08-28' and r['timeline'][3]['date']=='2026-08-31'
 assert r['verified']['asset_after']=='216420463.89'and r['method_promotions']==0
 r['timeline'].clear();assert len(baili_policy_followup(d,d['test_prior'])['timeline'])==6
 assert baili_policy_followup({},None)is None
@pytest.mark.parametrize('kind',['authority','company','prior','cash','timing','certification'])
def test_resealed_edits_do_not_erase_conflict_or_expand_certification(kind):
 d=fixture();p=d['baili_policy_followup']
 if kind=='authority':p['authorities'][0]['text']+='changed'
 elif kind=='company':next(s for s in d['twentyseventh_period_followup']['sources']if s['announcement_id']=='1225534310')['selected_pages']['10']='changed'
 elif kind=='prior':d['test_prior'].clear()
 elif kind=='cash':p['result']['verified']['cash_payment_proven']=True
 elif kind=='timing':p['result']['verified']['policy_after_h1_disclosure']=True
 else:p['result']['verified']['accounting_treatment_certified']=True
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):baili_policy_followup(d,d['test_prior'])
