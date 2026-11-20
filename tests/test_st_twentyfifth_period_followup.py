from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_twentyfifth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-twentyfifth-period-followup.json.gz').read_bytes()))
def test_source_bound_updates_and_arithmetic():
 d=fixture();old=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==old
 assert r['counts']['initial_coverage']==142 and len(r['chains'])==6
 assert len(r['event_windows'])==20
 assert sum(x['quarter_basis']=='nine_month_minus_h1' for x in r['financial_bridge'])==2
 assert '负' in r['chains'][4]['changed']
 assert '首次取得控制' in r['chains'][5]['changed']
 assert r['counts']['unfinished_windows']==5
 assert r['method_promotions']==0 and followup_view({},None)is None
@pytest.mark.parametrize('bad',['source','page','date','visual','prior','market','windows','future'])
def test_resealed_packet_changes_rejected(bad):
 d=fixture();p=d['twentyfifth_period_followup']
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

def test_cashflow_scope_and_market_windows():
 d=fixture();r=followup_view(d,d['test_prior']);windows=[w for g in r['event_windows']for w in g['windows']]
 assert len(windows)==60 and all(w['stock_quote_check']=='matched'for w in windows)
 assert sum(w['status']=='unfinished'for w in windows)==5
 cash=next(x for x in r['cashflow_components']if x['symbol']=='603789')
 assert cash['metrics']['other_operating_receipts']['Q3_calculated']=='-43265128.86'
 assert '不能解释为实际季度负收付款' in cash['unresolved_detail']
 net=next(x for x in r['financial_bridge']if x['symbol']=='603789'and x['metric']=='operating_cash')
 assert '倒差尚未解释' in net['quarter_boundary']

def test_resealed_cashflow_boundary_cannot_disappear():
 d=fixture();p=d['twentyfifth_period_followup'];p['cashflow_components'][2]['unresolved_detail']='resolved'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError,match='cashflow scope changed'):followup_view(d,d['test_prior'])
