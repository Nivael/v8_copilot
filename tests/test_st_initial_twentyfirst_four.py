from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_initial_twentyfirst_four import initial_twentyfirst_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-twentyfirst-four.json.gz').read_bytes()))
def test_fixed_cohort_risk_distinctions_and_prior_preserved():
 d=fixture();old=deepcopy(d);r=initial_twentyfirst_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']['after']==126 and r['counts']['remaining']==24
 assert [x['symbol']for x in r['rows']]==['600753','600759','600818','600889']
 assert len(r['visual_read'])==16 and r['quote_audit']['stock_endpoint_points']==12
 assert sum(x['has_timely_reading_facts']for x in r['inventory'])==126
 assert '满12个月' in r['rows'][0]['watch']
 assert '股权转让' in r['rows'][2]['known_at_anchor']
 assert '263638261.84' in r['rows'][3]['known_at_anchor']
 assert len(r['regulator_sources'])==1 and r['regulator_sources'][0]['document_dated_on']=='2026-04-28'
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
 assert initial_twentyfirst_four({},None,None)is None
@pytest.mark.parametrize('bad',['selection','source','page','date','review','cross','prior','regulator','catalog','market'])
def test_resealed_mutations_fail(bad):
 d=fixture();p=d['initial_twentyfirst_four']
 if bad=='selection':p['selection'].reverse()
 elif bad=='source':p['sources'].pop()
 elif bad=='page':p['sources'][0]['selected_pages']['1']='changed'
 elif bad=='date':p['sources'][0]['document_dated_on']='2026-01-01'
 elif bad=='review':p['visual_read'].pop()
 elif bad=='cross':p['cross_sources'][0]['sha256']='changed'
 elif bad=='regulator':p['regulator_sources'][0]['document_dated_on']='2026-05-01'
 elif bad=='catalog':p['catalog_scope']['current_complete']=False
 elif bad=='prior':d['test_prior']['inventory'][0]['has_timely_reading_facts']=False
 else:d['current_extension']['market_inputs']['through']='2026-11-20'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_twentyfirst_four(d,d['test_prior'],d['test_current'])
