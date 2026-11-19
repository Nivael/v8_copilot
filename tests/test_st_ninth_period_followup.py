import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_ninth_period_followup import followup_view

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-ninth-period-followup.json.gz').read_bytes()))
def test_preserves_cash_subjects_repeated_stages_and_unfinished_windows():
 x=fixture();v=followup_view(x,x['test_prior']);assert v['counts']==dict(files=23,pages=299,viewed_pages=28,initial_coverage=78,complete_windows=64,unfinished_windows=5,stock_endpoint_gaps=1)
 assert len(v['chains'])==13 and len(v['event_windows'])==23
 assert v['method_promotions']==0
@pytest.mark.parametrize('kind',['digest','prior','market','date','page','rehash','sha','visual','source_count','main_signature'])
def test_rejects_corrupted_evidence_even_after_packet_rehash(kind):
 x=fixture();p=x['ninth_period_followup'];s=p['sources'][0]
 if kind=='digest':p['content_digest']='bad'
 elif kind=='prior':p['prior_digest']='bad'
 elif kind=='market':p['market_digest']='bad'
 elif kind=='date':s['published_on']='2026-07-03'
 elif kind in ['page','rehash']:
  s['selected_pages']['1']+='forged'
  if kind=='rehash':s['page_hashes'][0]=sha256(s['selected_pages']['1'].encode()).hexdigest()
 elif kind=='sha':s['sha256']='bad'
 elif kind=='visual':p['visual_read']=[]
 elif kind=='source_count':p['sources'].pop()
 elif kind=='main_signature':next(s for s in p['sources']if s['announcement_id']=='1225429061')['document_dated_on']=None
 if kind!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(x,x['test_prior'])
def test_optional_packet():assert followup_view({},None)is None

def test_financial_report_event_dates_do_not_become_signature_dates():
 x=fixture();p=x['ninth_period_followup']
 for aid in ['1225504555','1225501314','1225523850','1225522498','1225504556']:
  assert next(s for s in p['sources']if s['announcement_id']==aid)['document_dated_on'] is None
 next(s for s in p['sources']if s['announcement_id']=='1225504556')['document_dated_on']='2026-03-26'
 p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(x,x['test_prior'])

def test_each_case_retains_primary_source_and_watched_boundaries():
 x=fixture();v=followup_view(x,x['test_prior']);sources={s['announcement_id']:s for s in v['sources']}
 for c in v['chains']:
  assert c['source'] in sources and c['open'] and (c.get('changed')or c.get('closed'))
  assert all(1<=n<=sources[c['source']]['pages']for n in c['pages'])
  for step in c.get('continuity',[]):assert step['source'] in sources and step['stage']
 text=json.dumps(v,ensure_ascii=False)
 for phrase in ['正式摘帽','发回重审','流拍','未经审计','归母','2025','2026']:assert phrase in text
 assert len(v['financial_bridge'])==16

def test_dongyi_phase_returns_compound_and_halt_does_not_create_a_trade():
 from decimal import Decimal as D
 x=fixture();v=followup_view(x,x['test_prior']);stages=v['dongyi_stages']['windows'];assert len(stages)==4
 factor=D(1)
 for r in stages[:3]:factor*=1+D(r['stock_pct'])/100
 assert abs((factor-1)*100-D(stages[3]['stock_pct']))<D('1e-20')
 assert stages[1]['market_days']==2
 window=next(e for e in v['event_windows']if e['aid']=='1225429061')['windows'][0]
 assert window['through']=='2026-07-17' and window['stock_pct']is None and window['stock_gap']
 assert window['market_pct']is not None and window['st_pct']is not None

def test_only_cash_quarter_values_are_explicitly_derived():
 x=fixture();v=followup_view(x,x['test_prior']);rows=v['financial_bridge']
 assert len([r for r in rows if r['reported_quarter_yuan']is None])==4
 assert all((r['reported_quarter_yuan']is None)==(r['metric']=='operating_cash')for r in rows)
 assert next(r for r in rows if r['symbol']=='002713'and r['metric']=='operating_cash')['quarter_yuan']=='-124949297.91'
 assert next(r for r in rows if r['symbol']=='002719'and r['metric']=='parent_profit')['quarter_yuan']=='-1191517.68'

def test_rejects_rehashed_market_that_rewrites_a_phase_endpoint():
 x=fixture();m=x['current_extension']['market_inputs']
 next(r for r in m['fixed_prices']if r['symbol']=='002713'and r['trade_date']=='2026-07-20')['close']=999
 p=x['ninth_period_followup'];p['market_digest']=digest(m);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises(ValueError):followup_view(x,x['test_prior'])
