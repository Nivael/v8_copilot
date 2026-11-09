import json
from pathlib import Path
from decimal import Decimal as D
import pytest
from canonical_json import digest
from st_tianji_conditions import tianji_conditions_view,scope_digest
from st_halt_price_crosscheck import scope_digest as price_scope

def seal(i):
 p=i['tianji_conditions'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def fixture():
 x=json.loads((Path(__file__).parent/'fixtures/earnings-warning.json').read_text());i=x['input'];p=i['tianji_conditions'];q=p['price_check'];q['scope_digest']=price_scope(i);q['content_digest']=digest({k:v for k,v in q.items()if k!='content_digest'});p['scope_digest']=scope_digest(i);seal(i);return i,x['daily']
def test_forecast_was_already_known_and_cash_only_later_turned_positive():
 i,d=fixture();v=tianji_conditions_view(i,d);h,q=v['reports'];assert v['forecast']['published_on']==v['warning']['published_on']=='2026-07-14'
 assert D(h['parent_profit'])>0>D(h['operating_cash']) and D(q['parent_profit'])>0 and D(q['operating_cash'])>0
 assert v['single_quarter']['operating_cash']=='265492706.13' and v['warning']['decision_made_on']is None and v['warning']['removal_estimated_on']is None
 assert not v['warning']['exception_supported']and v['warning']['decision_still_finds_misstatement']
def test_same_report_period_has_all_four_combinations_without_a_price_or_removal_ranking():
 i,d=fixture();v=tianji_conditions_view(i,d);rows=v['comparison'];assert len(rows)==v['independent_companies']==5
 assert len({r['combination']for r in rows})==4
 assert all(r['financial']['period_end']=='2026-09-30'and r['windows']['full']['market_days']==84 for r in rows)
 assert all(r['windows']['full']['stock_pct']<0<r['windows']['5']['stock_pct']for r in rows)
 assert len({(r['windows']['20']['anchor'],r['windows']['20']['through'])for r in rows})==1
 assert '不补入7月3日固定150'in v['selection']
def test_nonrecurring_cash_and_obtained_quote_checks_keep_different_scopes():
 i,d=fixture();v=tianji_conditions_view(i,d);q=v['reports'][1];assert D(q['parent_profit'])-D(q['deducted_profit'])==D('-27696597.67')
 assert D(v['cash']['opening'])+D(v['cash']['change'])==D(v['cash']['closing']);assert v['obtained_quotes_agree']
 assert v['quote_check']['valid_responses']==2 and v['quote_check']['quote_points']==250 and v['quote_check']['unique_traded_security_days']==125
 assert not v['quote_check']['all_available_prices_agree'] # Only the obtained Tencent raw/qfq checks; not four requested products.
@pytest.mark.parametrize('mutation',['anchor','auto','made','exception','forecast_cash','forecast_range','audit','period','source','rawquote','scope'])
def test_dates_coverage_reports_and_quotes_cannot_be_relabelled_as_certified(mutation):
 i,d=fixture();p=i['tianji_conditions']
 if mutation=='anchor':p['warning']['clock_anchor']='decision_received_on'
 if mutation=='auto':p['warning']['automatic_removal']=True
 if mutation=='made':p['warning']['decision_made_on']='2026-08-07'
 if mutation=='exception':p['warning']['exception_supported']=True
 if mutation=='forecast_cash':p['forecast']['operating_cash_forecast']='244426332.33'
 if mutation=='forecast_range':p['forecast']['parent_profit_high']='221000000'
 if mutation=='audit':p['reports'][1]['audited']=True
 if mutation=='period':p['reports'][1]['period_start']='2026-07-01'
 if mutation=='source':p['warning']['conditions_source']['page_text_hash']='0'*64
 if mutation=='rawquote':p['price_check']['sources'][0]['raw_text']+=' ';p['price_check']['content_digest']=digest({k:v for k,v in p['price_check'].items()if k!='content_digest'})
 if mutation=='scope':i['benchmarks']=[{'changed':True}]
 seal(i)
 with pytest.raises(ValueError):tianji_conditions_view(i,d)
def test_missing_actual_trade_endpoint_stays_empty_and_does_not_certify_quotes():
 i,d=fixture();next(r for r in i['fixed_prices']if r['symbol']=='002759'and r['trade_date']=='2026-07-03')['has_trade']=False;p=i['tianji_conditions'];p['scope_digest']=scope_digest(i);p['price_check']['scope_digest']=price_scope(i);p['price_check']['content_digest']=digest({k:v for k,v in p['price_check'].items()if k!='content_digest'});seal(i);v=tianji_conditions_view(i,d)
 assert v['comparison'][0]['windows']['full']['stock_pct']is None and not v['obtained_quotes_agree']
def test_optional_missing_packet_is_not_fabricated():assert tianji_conditions_view({},[])is None

def test_zero_profit_and_cash_are_not_mislabelled_as_loss_and_outflow():
 i,d=fixture();r=i['official_membership_audit']['issuer_checks'][0]['followup']['reports'][0];r['parent_profit']='0';r['operating_cash']='0';i['tianji_conditions']['scope_digest']=scope_digest(i);seal(i);v=tianji_conditions_view(i,d)
 assert next(r for r in v['comparison']if r['symbol']=='603021')['combination']=='profit_zero_cash_zero'
