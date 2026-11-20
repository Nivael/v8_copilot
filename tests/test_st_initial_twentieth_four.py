from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_initial_twentieth_four import initial_twentieth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-twentieth-four.json.gz').read_bytes()))
def test_fixed_cohort_risk_distinctions_and_prior_preserved():
 d=fixture();old=deepcopy(d);r=initial_twentieth_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']['after']==122 and r['counts']['remaining']==28
 assert [x['symbol']for x in r['rows']]==['600678','600734','600735','600745']
 assert len(r['visual_read'])==20 and r['quote_audit']['stock_endpoint_points']==12
 assert sum(x['has_timely_reading_facts']for x in r['inventory'])==122
 assert '争取目标' in r['rows'][1]['known_at_anchor']
 assert '首笔' in r['rows'][0]['known_at_anchor']
 assert len(r['source_conflicts'])==2
 assert r['regulator_sources']==[]
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
 assert initial_twentieth_four({},None,None)is None
@pytest.mark.parametrize('bad',['selection','source','page','date','review','cross','prior','regulator','catalog','market'])
def test_resealed_mutations_fail(bad):
 d=fixture();p=d['initial_twentieth_four']
 if bad=='selection':p['selection'].reverse()
 elif bad=='source':p['sources'].pop()
 elif bad=='page':p['sources'][0]['selected_pages']['1']='changed'
 elif bad=='date':p['sources'][0]['document_dated_on']='2026-01-01'
 elif bad=='review':p['visual_read'].pop()
 elif bad=='cross':p['cross_sources'][0]['sha256']='changed'
 elif bad=='regulator':p['regulator_sources'].append({'unexpected':True})
 elif bad=='catalog':p['catalog_scope']['current_complete']=False
 elif bad=='prior':d['test_prior']['inventory'][0]['has_timely_reading_facts']=False
 else:d['current_extension']['market_inputs']['through']='2026-11-20'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_twentieth_four(d,d['test_prior'],d['test_current'])
