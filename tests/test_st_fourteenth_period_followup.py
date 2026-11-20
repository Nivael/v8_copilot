from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_fourteenth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-fourteenth-period-followup.json.gz').read_bytes()))

def test_updates_keep_removal_cash_and_source_conflicts_separate():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert r['counts']['initial_coverage']==98 and r['counts']['complete_windows']==69
 assert r['counts']['unfinished_windows']==9 and r['counts']['stock_endpoint_gaps']==1
 assert len(r['chains'])==10 and len(r['financial_bridge'])==16
 assert r['low_price_review']['rows'][-1]['consecutive_below_one']==6
 assert r['financial_source_conflict']['status']=='unresolved_source_internal_conflict'
 assert any('投标保证保险保单' in c['open'] for c in r['chains'])
 assert r['method_promotions']==0

@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','page','review','window','low_price','financial_conflict'])
def test_resealed_changes_are_rejected(bad):
 d=fixture();p=d['fourteenth_period_followup'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=99
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad=='missing':p['sources'].pop()
 elif bad=='identity':s['symbol']='999999'
 elif bad=='date':s['published_on']='2026-11-20'
 elif bad=='page':s['selected_pages']['1']='changed'
 elif bad=='review':p['visual_read'].pop()
 elif bad=='window':p['event_windows_digest']='changed'
 else:p[bad+'_digest']='changed'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(d,d['test_prior'])
