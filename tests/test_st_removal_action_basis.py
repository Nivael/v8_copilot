from pathlib import Path
import copy,json,gzip
import pytest
from canonical_json import digest
from st_removal_action_basis import action_basis_view,scope_digest,window_support
from st_removal_era_comparison import removal_era_comparison

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/removal-action-basis.json.gz').read_bytes()))
def seal(i):
 p=i['removal_action_basis'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_four_actions_not_three_and_two_mirrors_never_become_official():
 i=fixture();old=copy.deepcopy(i);b=action_basis_view(i);assert i==old
 assert tuple(b[k]for k in ('issuers','actions_count','files','pages','official_files','mirror_files','traded_security_days','quote_points','new_market_queries'))==(3,4,4,11,2,2,367,734,0)
 assert all(not r['additive_mismatch_dates']for r in b['rows'])
 rows={r['symbol']:r for r in b['rows']};assert len(rows['600360']['actions'])==2
 assert [(a['reference'],a['factor_on'])for a in rows['600360']['actions']]==[('12.98','7.9574'),('9.27','7.9917')]
 assert rows['603580']['actions'][0]['cash_per_share']=='0.082'
 assert [(r['symbol'],len(r['direct_difference_dates']))for r in b['rows']]==[('600360',116),('000668',33),('603580',65)]

def test_same_issuer_support_changes_mean_sign_without_claiming_most_win():
 i=fixture();v=removal_era_comparison(i,i['test_daily']);a=v['summaries']['20']['pre']['from_resume_close']['all'];b=v['summaries']['40']['pre']['from_resume_close']['all']
 assert(a['count'],a['positive'],a['negative'])==(37,11,26)
 assert(b['count'],b['positive'],b['negative'])==(37,15,22)
 assert b['mean_pct']==pytest.approx(4.083203931743865)and b['median_pct']==pytest.approx(-7.657657657657658)
 assert v['prior_version']==i['removal_action_basis']['prior_comparison']and v['prior_version']['summaries']['40']['pre']['from_resume_close']['all']['mean_pct']<0
 assert v['summaries']['20']['post']==v['prior_version']['summaries']['20']['post']

def test_strict_official_filter_checks_action_proof_inside_the_window():
 i=fixture();v=removal_era_comparison(i,i['test_daily']);r={r['symbol']:r for r in v['rows']}
 assert r['600360']['windows']['20']['from_resume_close']['action_support']['has_mirror']is False
 assert r['603580']['windows']['40']['from_resume_close']['action_support']['has_mirror']is True
 assert v['summaries']['40']['pre']['from_resume_close']['official_only']['count']==31
 assert v['summaries']['20']['pre']['from_resume_close']['official_only']['count']==32
 assert r['603580']['windows']['5']['from_resume_close']['status']=='nontraded_or_missing_endpoint'and r['603517']['windows']['20']['from_resume_close']['status']=='insufficient_followup'
 assert window_support('000711',r['600360']['windows']['20']['from_resume_close'],v['action_basis'])is None

@pytest.mark.parametrize('bad',['scope','digest','count','symbol','date','cash','shares','total','record','receipt','page','host','mirror_level','factor','raw','published'])
def test_corruption_or_issuer_scope_does_not_receive_support(bad):
 i=fixture();p=i['removal_action_basis'];r=p['actions'][0];s=next(s for s in p['sources']if s['announcement_id']==r['source_id'])
 if bad=='scope':i['through']='2026-11-05'
 elif bad=='digest':r['cash_per_share']='0.022'
 elif bad=='count':p['actions'].pop()
 elif bad=='symbol':r['symbol']='600361'
 elif bad=='date':r['ex_on']='2026-06-09'
 elif bad=='cash':r['cash_per_share']='0.21'
 elif bad=='shares':r['total_shares']='960295305'
 elif bad=='total':r['declared_total']='20166201.39'
 elif bad=='record':r['record_on']='2026-06-04'
 elif bad=='receipt':r['personal_receipt_verified']=True
 elif bad=='page':s['selected_pages']['1']+='changed'
 elif bad=='host':s['url']='https://example.com/notice.pdf'
 elif bad=='mirror_level':next(s for s in p['sources']if not s['host_is_official'])['host_is_official']=True
 elif bad=='factor':next(c for c in i['dynamic_reference_audit']['original_prices']['companies']if c['symbol']=='600360')['rows'][-1]['adj_factor']=8
 elif bad=='raw':next(s for s in i['dynamic_reference_audit']['sources']if s['symbol']=='600360')['sha256']='0'*64
 elif bad=='published':r['published_on']='2026-06-09'
 if bad not in ('scope','digest'):seal(i)
 with pytest.raises((ValueError,KeyError)):action_basis_view(i)

def test_legacy_has_no_unearned_support():assert action_basis_view({})is None
