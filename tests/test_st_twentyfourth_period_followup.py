from pathlib import Path
from copy import deepcopy
import gzip,json
import pytest
from canonical_json import digest
from st_twentyfourth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-twentyfourth-period-followup.json.gz').read_bytes()))
def test_source_bound_updates_and_arithmetic():
 d=fixture();old=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==old
 assert r['counts']['initial_coverage']==138 and len(r['chains'])==6
 assert len(r['event_windows'])==24
 assert sum(x['quarter_basis']=='nine_month_minus_h1' for x in r['financial_bridge'])==2
 assert '不能重复计算' in r['chains'][4]['changed']
 assert '仍待交易所审核' in r['chains'][5]['changed']
 assert r['counts']['unfinished_windows']==15
 assert r['method_promotions']==0 and followup_view({},None)is None
@pytest.mark.parametrize('bad',['source','page','date','visual','prior','market','windows','future'])
def test_resealed_packet_changes_rejected(bad):
 d=fixture();p=d['twentyfourth_period_followup']
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

def test_quote_conflicts_and_nontraded_are_visible():
 d=fixture();r=followup_view(d,d['test_prior']);windows=[w for g in r['event_windows'] for w in g['windows']]
 assert len(windows)==72
 assert sum(w['stock_quote_check']=='not_calculable' for w in windows)==3
 assert sum(w['stock_quote_check']=='matched' for w in windows)==60
 conflicts=[w for w in windows if w['stock_quote_check']=='price_basis_or_precision_difference']
 assert len(conflicts)==9 and all('跨源待核' in w['stock_quote_boundary'] for w in conflicts)
 assert all(w['stock_pct'] is None and w['stock_gap'] for w in windows if w['stock_quote_check']=='not_calculable')

def test_resealed_quote_conflict_cannot_be_promoted():
 d=fixture();p=d['twentyfourth_period_followup'];r=next(r for r in p['quote_reviews'] if r['status']!='matched');r['status']='matched'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError,match='quote reviews changed'):followup_view(d,d['test_prior'])
