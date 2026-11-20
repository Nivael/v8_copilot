from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_initial_twentyfifth_four import initial_twentyfifth_four

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-initial-twentyfifth-four.json.gz').read_bytes()))
def test_cohort_reading_and_quote_conflicts_preserved():
 d=fixture();old=deepcopy(d);r=initial_twentyfifth_four(d,d['test_prior'],d['test_current']);assert d==old
 assert r['counts']['after']==142 and r['counts']['remaining']==8
 assert len(r['visual_read'])==26
 assert r['quote_audit']['stock_endpoint_points']==12
 assert r['quote_audit']['stock_return_windows']==8
 assert all(p['status']=='matched'for x in r['quote_audit']['stock_reviews']for p in x['points'])
 assert '商业实质' in r['rows'][1]['known_at_anchor']
 assert '9月29日' in r['rows'][2]['watch'] and r['source_conflicts']
 assert not d['initial_twentyfifth_four']['catalog_scope']['origin_complete']
 assert d['initial_twentyfifth_four']['catalog_scope']['official_pdf_without_catalog']==['1224561595','603825_20250911_FG3F']
 assert r['method_promotions']==0 and not r['full_membership_certification_added']
 assert initial_twentyfifth_four({},None,None)is None
@pytest.mark.parametrize('bad',['selection','source','page','date','review','cross','prior','regulator','catalog','market'])
def test_resealed_mutations_fail(bad):
 d=fixture();p=d['initial_twentyfifth_four']
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
 with pytest.raises(ValueError):initial_twentyfifth_four(d,d['test_prior'],d['test_current'])

@pytest.mark.parametrize('field',['published_on','title','raw_item','url'])
def test_official_pdf_identity_cannot_be_resealed(field):
 d=fixture();p=d['initial_twentyfifth_four'];s=next(s for s in p['sources']if s['announcement_id']=='603825_20250911_FG3F')
 s[field]={} if field=='raw_item' else 'changed'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError,match='official PDF identity'):initial_twentyfifth_four(d,d['test_prior'],d['test_current'])
