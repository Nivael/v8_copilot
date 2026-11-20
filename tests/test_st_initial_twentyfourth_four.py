from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_initial_twentyfourth_four import initial_twentyfourth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-twentyfourth-four.json.gz').read_bytes()))
def test_cohort_reading_and_quote_conflicts_preserved():
 d=fixture();old=deepcopy(d);r=initial_twentyfourth_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']['after']==138 and r['counts']['remaining']==12
 assert len(r['visual_read'])==19
 assert r['quote_audit']['stock_endpoint_points']==10
 assert r['quote_audit']['stock_return_windows']==6
 review=next(x for x in r['quote_audit']['stock_reviews']if x['symbol']=='603517')
 assert [x['status']for x in review['points']]==['price_basis_conflict','price_basis_conflict','matched']
 assert all(w['return_pct']is None for w in review['windows'])
 assert '余90%'in r['rows'][3]['known_at_anchor']
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
 assert initial_twentyfourth_four({},None,None)is None
@pytest.mark.parametrize('bad',['selection','source','page','date','review','cross','prior','regulator','catalog','market'])
def test_resealed_mutations_fail(bad):
 d=fixture();p=d['initial_twentyfourth_four']
 if bad=='selection':p['selection'].reverse()
 elif bad=='source':p['sources'].pop()
 elif bad=='page':p['sources'][0]['selected_pages']['1']='changed'
 elif bad=='date':p['sources'][0]['document_dated_on']='2026-01-01'
 elif bad=='review':p['visual_read'].pop()
 elif bad=='cross':p['cross_sources'][0]['sha256']='changed'
 elif bad=='regulator':p['regulator_sources'].append({'changed':True})
 elif bad=='catalog':p['catalog_scope']['current_complete']=False
 elif bad=='prior':d['test_prior']['inventory'][0]['has_timely_reading_facts']=False
 else:d['current_extension']['market_inputs']['through']='2026-11-20'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):initial_twentyfourth_four(d,d['test_prior'],d['test_current'])
