from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_fifteenth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-fifteenth-period-followup.json.gz').read_bytes()))

def test_updates_preserve_legal_accounting_and_fulfillment_boundaries():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert r['counts']['initial_coverage']==102 and r['counts']['complete_windows']==64
 assert r['counts']['unfinished_windows']==11 and r['counts']['stock_endpoint_gaps']==2
 assert len(r['chains'])==10 and len(r['financial_bridge'])==16
 assert any('不是全部摘帽' in c['open']for c in r['chains'])
 assert any('旧案撤诉不等于新案终结' in c['open']for c in r['chains'])
 assert any('预计约600万元收益' in c['open']for c in r['chains'])
 assert any('正式批准生效证据缺口' in c['open']for c in r['chains'])
 assert sum(x['reported_h1_yoy_pct']is None for x in r['financial_bridge'])==10
 assert sum(x['reported_h1_yoy_marker']=='空白'for x in r['financial_bridge'])==3
 assert sum(x['reported_quarter_yuan']is not None for x in r['financial_bridge'])==13
 assert r['method_promotions']==0

@pytest.mark.parametrize('bad',['prior','market','duplicate','missing','identity','date','page','review','window'])
def test_resealed_changes_are_rejected(bad):
 d=fixture();p=d['fifteenth_period_followup'];s=p['sources'][0]
 if bad=='prior':d['test_prior']['counts']['after']=103
 elif bad=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif bad=='duplicate':p['sources'].append(deepcopy(s))
 elif bad=='missing':p['sources'].pop()
 elif bad=='identity':s['symbol']='999999'
 elif bad=='date':s['published_on']='2026-11-20'
 elif bad=='page':s['selected_pages']['1']='changed'
 elif bad=='review':p['visual_read'].pop()
 else:p['event_windows_digest']='changed'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(d,d['test_prior'])
