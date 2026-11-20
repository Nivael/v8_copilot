from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_twentieth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-twentieth-period-followup.json.gz').read_bytes()))
def test_source_bound_updates_and_preserved_difference():
 d=fixture();old=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==old
 assert r['counts']['initial_coverage']==122 and len(r['chains'])==6
 assert len(r['event_windows'])==23 and len(r['phase_comparisons'])==36
 assert '强制执行申请' in r['chains'][0]['changed']
 assert '银行承兑汇票' in r['chains'][1]['changed']
 assert all(x['quarter_difference_yuan'] in [None,'0.00'] for x in r['financial_bridge'])
 assert sum(x['quarter_basis']=='nine_month_minus_h1' for x in r['financial_bridge'])==4
 assert next(x for x in r['financial_bridge'] if x['symbol']=='600734')['prior_basis']=='restated'
 assert r['method_promotions']==0 and followup_view({},None)is None
@pytest.mark.parametrize('bad',['source','page','date','visual','prior','market','windows','future'])
def test_resealed_packet_changes_rejected(bad):
 d=fixture();p=d['twentieth_period_followup']
 if bad=='source':p['sources'].pop()
 elif bad=='page':p['sources'][0]['selected_pages']['1']='changed'
 elif bad=='date':p['sources'][0]['document_dated_on']='2026-01-01'
 elif bad=='visual':p['visual_read'].pop()
 elif bad=='prior':d['test_prior']['counts']['after']=119
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='windows':p['event_windows_digest']='changed'
 else:p['sources'][0]['published_on']='2026-11-20'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(d,d['test_prior'])
