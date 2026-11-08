from copy import deepcopy
from hashlib import sha256
from decimal import Decimal as D
import json
import pytest
from canonical_json import digest
from test_st_removal_cohort import fixture as cohort_fixture
from st_member_transitions import membership_scope_digest
from st_removal_cohort import scope_digest as cohort_scope,removal_cohort_view
from st_juewei_adjustment import scope_digest,juewei_adjustment_view

def fixture():
 i,d=cohort_fixture();packet=i['removal_cohort'];company=next(c for c in packet['original_prices']['companies']if c['symbol']=='600002');company['symbol']='603517';company['qfq_normalization_factor']=1.6394
 for row in company['rows']:
  day=row['date'];row['adj_factor']=1.5997 if day<'2026-10-23' else 1.6394
  price={'2026-09-24':11.43,'2026-10-09':11.21,'2026-10-16':10.87,'2026-10-20':10.78}.get(day,10.33 if day<'2026-10-23' else 10.13)
  row['raw_close']=price if row['has_trade']else None
  row['qfq_close']=float(D(str(price))*D(str(row['adj_factor']))/D('1.6394')) if row['has_trade'] else None
 for row in i['fixed_prices']:
  if row['symbol']=='600002':
   row['symbol']='603517';base=next(x for x in company['rows']if x['date']==row['trade_date']);row['close']=base['qfq_close'] or 10.606770159814566
 for row in i['members']:
  if row['symbol']=='600002':row['symbol']='603517'
 t=next(t for t in i['member_transitions']['rows']if t['symbol']=='600002');t['symbol']='603517'
 tr=i['member_transitions'];tr['membership_scope_digest']=membership_scope_digest(i);tr['content_digest']=digest({k:v for k,v in tr.items()if k!='content_digest'})
 for ref in packet['sources']:
  if ref['symbol']!='600002':continue
  ref['symbol']='603517';key=ref['key'];qs=[]
  for row in company['rows']:
   if not row['has_trade']:continue
   value=D(str(row['raw_close']))-(D('.25')if key.endswith('qfq')and row['date']<'2026-10-23'else 0);qs.append([row['date'],'1',str(value),'20','1','100'])
  ref['raw_text']=json.dumps({'data':{'sh603517':{'qt':{'sh603517':['name','name','603517']},'day':qs,'qfqday':qs}}});ref['sha256']=sha256(ref['raw_text'].encode()).hexdigest()
 packet['scope_digest']=cohort_scope(i);packet['content_digest']=digest({k:v for k,v in packet.items()if k!='content_digest'})
 sources=[{'announcement_id':aid,'symbol':'603517','sha256':sha256(aid.encode()).hexdigest(),'url':'https://example.test/'+aid+'.pdf','title':'official','pages':pages}for aid,pages in [('1225610029',4),('1225610010',2),('1225610007',6)]]
 p={'symbol':'603517','through':i['through'],'scope_digest':scope_digest(i),'prior_snapshot_digest':'a'*64,'sources':sources,'facts':[{'published_on':'2026-10-19','source':{**sources[0],'page':2},'text':'分派与口径'}],'action':{'published_on':'2026-10-19','record_date':'2026-10-22','ex_date':'2026-10-23','scheduled_payment_on':'2026-10-23','actual_personal_receipt_verified':False,'total_shares':'606001936','repurchase_shares':'8515600','eligible_shares':'597486336','eligible_cash_per_share':'0.25','reported_rounded_reference_cash':'0.25','scheduled_total_yuan':'149371584.00','prior_scheduled_total_yuan':'151500484.00','share_change_ratio':'0'},'opinion_example':{'date':'2026-09-24','raw_close':'11.43','reported_reference':'11.18'},'ex_date_cache_rows':[{'api':'daily','trade_date':'2026-10-23','rows':[{'ts_code':'603517.SH','pre_close':10.08,'close':10.13,'vol':100}]}]}
 p['content_digest']=digest(p);i['juewei_adjustment']=p;return i,d

def seal(i):
 p=i['juewei_adjustment'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})

def test_two_bases_can_be_reconstructed_without_making_direct_quotes_equal():
 i,d=fixture();v=juewei_adjustment_view(i);assert v['comparison_reconstruction_supported'];assert v['direct_price_difference_count']>0 and not v['normalized_mismatch_dates'];assert v['calculation']['raw_price_change_pct']<0<v['calculation']['reference_change_pct'];assert v['calculation']['formula_factor_rounded']=='1.6394';assert v['five_day_examples']['before']['factor_pct']!=v['five_day_examples']['before']['additive_pct']

def test_rounded_reference_and_legal_example_keep_distinct_precision_and_dates():
 i,d=fixture();v=juewei_adjustment_view(i);c=v['calculation'];assert D(c['virtual_cash_per_total_share'])!=D('.25');assert c['opinion_example_actual_cent']==c['opinion_example_virtual_cent']=='11.18';assert D(c['opinion_unrounded_reference_effect_pct'])>0;assert c['previous_session']=='2026-10-22' and v['opinion_example']['date']=='2026-09-24'

def test_normalization_expands_current_pairing_but_preserves_strict_direct_history():
 i,d=fixture();v=removal_cohort_view(i,d);assert v['strict_quote_summaries']['5']['paired_count']==1 and v['summaries']['5']['paired_count']==2;r=next(r for r in v['rows']if r['symbol']=='603517');assert not r['windows']['5']['before']['quote_endpoint_supported'] and r['windows']['5']['before']['comparison_supported'];assert r['windows']['5']['before']['comparison_support_kind']=='same_factor_reconstruction_from_raw'

def test_one_unexplained_additive_quote_breaks_reconstruction_support():
 i,d=fixture();ref=next(r for r in i['removal_cohort']['sources']if r['symbol']=='603517'and r['key']=='tencent_qfq');x=json.loads(ref['raw_text']);x['data']['sh603517']['qfqday'][0][2]='9.99';ref['raw_text']=json.dumps(x);ref['sha256']=sha256(ref['raw_text'].encode()).hexdigest();p=i['removal_cohort'];p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'});i['juewei_adjustment']['scope_digest']=scope_digest(i);seal(i);v=juewei_adjustment_view(i);assert not v['comparison_reconstruction_supported'] and v['status']=='unresolved';assert '暂不能'in v['answer'];assert removal_cohort_view(i,d)['summaries']['5']['paired_count']==1

@pytest.mark.parametrize('key,value',[('actual_personal_receipt_verified',True),('eligible_shares','606001936'),('record_date','2026-10-21')])
def test_receipt_or_share_or_calendar_claims_cannot_be_silently_changed(key,value):
 i,d=fixture();i['juewei_adjustment']['action'][key]=value;seal(i)
 with pytest.raises(ValueError):juewei_adjustment_view(i)

def test_optional_absent():assert juewei_adjustment_view({})is None
