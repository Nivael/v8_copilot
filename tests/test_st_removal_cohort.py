from datetime import date,timedelta
from hashlib import sha256
import json
import pytest
from canonical_json import digest
from st_member_transitions import membership_scope_digest
from st_removal_cohort import removal_cohort_view,scope_digest

def fixture(same_date=False):
 start=date(2026,5,6);end=date(2026,11,6);cal=[(start+timedelta(days=n)).isoformat() for n in range((end-start).days+1) if (start+timedelta(days=n)).weekday()<5];targets=[];companies=[];sources=[];fixed=[];members=[]
 for s,halt,resume in [('600001','2026-08-28','2026-08-31'),('600002','2026-08-28' if same_date else '2026-10-19','2026-08-31' if same_date else '2026-10-20')]:
  source={'title':'official','url':'https://example.test/official.pdf','page':1,'sha256':'a'*64}
  targets.append({'symbol':s,'anchor_name':'ST测试'+s,'new_name':'测试'+s,'status':'warning_removed','announced_on':halt,'suspend_on':halt,'effective_on':resume,'provider_last_st':halt,'provider_first_absent':resume,'warning_removed':'other','facts':[{'published_on':halt,'text':'停复牌与撤销','source':source}]})
  rows=[{'date':d,'raw_close':None if d==halt else 1.,'qfq_close':None if d==halt else 1.,'volume':0 if d==halt else 100,'has_trade':d!=halt,'adj_factor':1.} for d in cal]
  companies.append({'symbol':s,'rows':rows,'qfq_normalization_date':cal[-1],'qfq_normalization_factor':1.})
  fixed += [{'symbol':s,'trade_date':r['date'],'close':r['qfq_close'] or 1.,'has_trade':r['has_trade']} for r in rows]
  members += [{'symbol':s,'trade_date':d} for d in cal if d<resume]
  qs=[[r['date'],'1','1','1','1','100'] for r in rows if r['has_trade']];ticker='sh'+s;raw=json.dumps({'data':{ticker:{'qt':{ticker:['name','name',s]},'day':qs,'qfqday':qs}}})
  sources += [{'symbol':s,'key':key,'raw_text':raw,'sha256':sha256(raw.encode()).hexdigest(),'url':'https://example.test/quote','observed_at':'2026-11-09'} for key in ('tencent_raw','tencent_qfq')]
 i={'calendar':cal,'through':cal[-1],'fixed_prices':fixed,'members':members,'activities':[],'benchmarks':[]};transition={'anchor':'2026-07-03','through':cal[-1],'rows':targets,'membership_scope_digest':membership_scope_digest(i)};transition['content_digest']=digest(transition);i['member_transitions']=transition
 p={'scope_digest':scope_digest(i),'original_prices':{'calendar':cal,'through':cal[-1],'companies':companies},'sources':sources,'failed_requests':[]};p['content_digest']=digest(p);i['removal_cohort']=p
 return i,[{'date':d,'market_pct':0.,'return_pct':0.}for d in cal]
def seal(i):
 p=i['removal_cohort'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})

def test_same_paired_denominator_and_unfinished_company_are_retained():
 i,d=fixture();v=removal_cohort_view(i,d);s=v['summaries']['20'];assert v['cohort_total']==2 and len(v['rows'])==2;assert s['paired_symbols']==['600001'];assert s['before']['count']==s['after']['count']==1;assert s['not_paired'][0]['symbol']=='600002' and s['not_paired'][0]['after_status']=='insufficient_followup'

def test_nontraded_first_market_day_is_not_zero_and_resume_close_is_another_window():
 i,d=fixture();v=removal_cohort_view(i,d);a=v['rows'][0]['windows']['1'];assert a['after']['stock_pct'] is None and a['after']['market_pct']==0.;assert a['after']['stock_traded_days']==0;assert a['from_resume_close']['stock_pct']==0.;assert a['from_resume_close']['anchor']=='2026-08-31';assert v['summaries']['1']['paired_count']==0

def test_conflicting_adjusted_endpoints_preserve_reference_but_do_not_certify_pair():
 i,d=fixture();ref=next(x for x in i['removal_cohort']['sources'] if x['symbol']=='600001' and x['key']=='tencent_qfq');x=json.loads(ref['raw_text']);r=next(r for r in x['data']['sh600001']['qfqday'] if r[0]=='2026-08-27');r[2]='1.02';ref['raw_text']=json.dumps(x);ref['sha256']=sha256(ref['raw_text'].encode()).hexdigest();seal(i);v=removal_cohort_view(i,d);w=v['rows'][0]['windows']['20'];assert w['after']['stock_pct']==0 and not w['after']['quote_endpoint_supported'];assert w['after']['checked_qfq_pct']<0;assert v['summaries']['20']['raw_pairable_count']==1 and v['summaries']['20']['paired_count']==0;assert v['quote_summary']['raw_agree_companies']==2 and v['quote_summary']['qfq_agree_companies']==1

def test_shared_dates_are_not_counted_as_independent_time_windows():
 i,d=fixture(True);v=removal_cohort_view(i,d);s=v['summaries']['20'];assert s['paired_count']==2 and s['date_group_count']==1 and s['overlapping_stock_pairs']==s['possible_stock_pairs']==1 and s['max_overlap_days']==20

def test_original_price_and_membership_scope_cannot_be_changed_under_old_receipt():
 i,d=fixture();i['fixed_prices'][0]['close']=5.
 with pytest.raises(ValueError,match='source/scope'):removal_cohort_view(i,d)

def test_source_bytes_and_subject_identity_are_bound():
 i,d=fixture();i['removal_cohort']['sources'][0]['raw_text']+=' ';seal(i)
 with pytest.raises(ValueError,match='original changed'):removal_cohort_view(i,d)

def test_optional_absent():assert removal_cohort_view({},[]) is None
