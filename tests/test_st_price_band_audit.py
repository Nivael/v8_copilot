import gzip,json
from pathlib import Path
from decimal import Decimal as D
import pytest
from canonical_json import digest
from st_price_band_audit import price_band,price_band_view,scope_digest

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/price-band-audit.json.gz').read_bytes()))
def seal(i):
 p=i['price_band_audit'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})

def test_rounding_and_minimum_tick_not_percentage_hardcut():
 assert price_band('.91','.05')==(D('.96'),D('.86'))
 assert price_band('.95','.05')==(D('1.00'),D('.90'))
 assert price_band('.01','.05')==(D('.02'),D('.01'))
 assert price_band('7.42','.10')==(D('8.16'),D('6.68'))

def test_real_frozen_observations_and_equal_windows():
 i=fixture();before=digest(i);v=price_band_view(i);assert digest(i)==before
 a,b=v['windows']['all'].values()
 assert(a['days'],a['observations'],a['over5'],a['old_crossings'],a['actual_limit_closes'])==(41,6910,821,0,1754)
 assert(b['days'],b['observations'],b['over5'],b['old_crossings'],b['actual_limit_closes'])==(84,12099,1306,1240,346)
 assert v['observations']==19009 and v['provider_responses']==250
 assert v['windows']['20']['after']['old_crossings']==544
 assert v['windows']['40']['before']['observations']==6725
 assert v['windows']['40']['after']['old_crossings']==780
 assert len(v['reference_changes'])==12 and sum(bool(r['conflict'])for r in v['reference_changes'])==1
 assert next(r for r in v['reference_changes']if r['conflict'])['symbol']=='000821'
 assert len(v['previous_quote_unknown'])==1 and v['previous_quote_unknown'][0]['symbol']=='002731'
 assert len(v['former_st_resumptions'])==37 and sum(r['old_crossing']for r in v['former_st_resumptions'])==16
 assert sum(r['limit_api_pre_close']is None for r in v['api_reference_differences'])==6
 assert len(v['api_reference_differences'])==14
 assert v['new_cash']['source']['source_format']=='pdf_mirror'

@pytest.mark.parametrize('bad',['digest','scope','receipt','limits','raw','cash','mirror','page','member','action','unknown_ref'])
def test_mutations_do_not_silently_get_verified(bad):
 i=fixture();p=i['price_band_audit']
 if bad=='digest':p['rule_day']='2026-07-05'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='receipt':p['provider_replay'][0]['selected_digest']='0'*64
 elif bad=='limits':next(r for r in i['activities']if r['trade_date']=='2026-07-06'and r['volume']>0)['up_limit']+=.01
 elif bad=='raw':next(s for s in i['dynamic_reference_audit']['sources']if s['key']=='tencent_raw')['sha256']='0'*64
 elif bad=='cash':p['new_cash']['cash_per_share']='0.8'
 elif bad=='mirror':p['new_cash']['source']['host_is_official']=True
 elif bad=='page':p['new_cash']['source']['selected_pages']['1']+='changed'
 elif bad=='member':i['members'].pop()
 elif bad=='action':i['remaining_basis']['rows']=[r for r in i['remaining_basis']['rows']if r['symbol']!='000821']
 elif bad=='unknown_ref':p['limit_api_pre_close_differences'][0]['daily_reference']='999'
 if bad not in ('digest','scope'):seal(i)
 with pytest.raises((ValueError,KeyError,StopIteration)):price_band_view(i)

def test_legacy_has_no_unearned_audit():assert price_band_view({})is None
