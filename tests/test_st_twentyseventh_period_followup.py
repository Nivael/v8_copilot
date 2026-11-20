from pathlib import Path
from copy import deepcopy
from decimal import Decimal as D
import gzip,json
import pytest
from canonical_json import digest
from st_twentyseventh_period_followup import followup_view

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/st-twentyseventh-period-followup.json.gz').read_bytes()))
def test_verified_progress_keeps_disclosure_cash_earnings_and_market_separate():
 d=fixture();before=deepcopy(d);r=followup_view(d,d['test_prior']);assert d==before
 assert len(r['chains'])==6 and len(r['financial_bridge'])==15
 windows=[w for g in r['event_windows']for w in g['windows']]
 assert len(windows)==69 and sum(w['status']=='unfinished'for w in windows)==9
 assert all(w['stock_quote_check']=='matched'and w['stock_pct']is not None for w in windows)
 baili=next(x for x in r['financial_bridge']if x['symbol']=='603959'and x['metric']=='parent_profit')
 assert baili['reported_quarter_yuan']=='-128830967.14'and baili['quarter_yuan']=='-128830967.13'and D(baili['quarter_difference_yuan'])==D('.01')
 assert not any(x['symbol']=='603959'and x['metric']=='recurring_profit'for x in r['financial_bridge'])
 assert sum(x['reported_quarter_yuan']is None for x in r['financial_bridge'])==3
 assert r['index_review']['matched']==48 and r['index_review']['conflicts']==0
 b=next(x for x in r['focused_comparisons']['rows']if x['symbol']=='603959');w=next(x for x in b['after']if x['requested_days']==5)
 assert D(w['stock_pct'])<0<D(w['st_pct']) and D(w['market_pct'])>0
 assert r['method_promotions']==0 and r['counts']['initial_coverage']==150
 assert followup_view({},None)is None

@pytest.mark.parametrize('change',['source','page','visual','market','prior','windows','quote','cash','pre_event','index'])
def test_resealed_changes_cannot_override_verified_scope(change):
 d=fixture();p=d['twentyseventh_period_followup']
 if change=='source':p['sources'][0]['sha256']='bad'
 elif change=='page':p['sources'][0]['selected_pages']['1']='bad'
 elif change=='visual':p['visual_read'].pop()
 elif change=='market':d['current_extension']['market_inputs']['through']='2026-11-20'
 elif change=='prior':d['test_prior']['counts']['after']=146
 elif change=='windows':p['event_windows_digest']='bad'
 elif change=='quote':p['quote_reviews'][0]['cross_return_pct']='0'
 elif change=='cash':p['cashflow_components'].append({'bad':True})
 elif change=='pre_event':p['focused_comparisons']['rows'][0]['before_5_sessions']['stock_pct']='0'
 else:p['index_review']['rows'][0]['official']='0'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(d,d['test_prior'])
