from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_jingji_dividend_followup import jingji_dividend_followup

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-jingji-dividend-followup.json.gz').read_bytes()))
def test_rounded_equality_does_not_resolve_input_or_issuer_conflict():
 d=fixture();before=deepcopy(d);r=jingji_dividend_followup(d,d['test_prior']);assert d==before;c=r['calculation']
 assert c['printed_ten_truncated_6']=='0.329999'and c['total_ten_truncated_6']=='0.326688'
 assert c['eb_using_reported_reference_exact']!=c['eb_using_eligible_cash_exact']
 assert c['eb_using_reported_reference_rounded']==c['eb_using_eligible_cash_rounded']=='14.47'
 assert not r['issuer_correction_verified']and not r['unique_input_identified']and r['method_promotions']==0
 r['calculation'].clear();assert jingji_dividend_followup(d,d['test_prior'])['calculation']
 assert jingji_dividend_followup({},None)is None
@pytest.mark.parametrize('kind',['source','prior','denominator','correction','unique'])
def test_resealed_changes_cannot_rewrite_printed_denominator_or_claim_certification(kind):
 d=fixture();p=d['jingji_dividend_followup']
 if kind=='source':p['source']['texts'][2]='changed'
 elif kind=='prior':d['test_prior'].clear()
 elif kind=='denominator':p['result']['calculation']['printed_denominator']='622874778'
 elif kind=='correction':p['result']['issuer_correction_verified']=True
 else:p['result']['unique_input_identified']=True
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):jingji_dividend_followup(d,d['test_prior'])
