import copy,gzip,json
from pathlib import Path
import pytest
from canonical_json import digest
from st_pre_rule_membership import pre_rule_membership_view,scope_digest,boundary_price_inputs

def fixture():return json.loads(gzip.decompress((Path(__file__).parent/'fixtures/pre-rule-membership.json.gz').read_bytes()))
def seal(i):
 p=i['pre_rule_membership'];p['scope_digest']=scope_digest(i);p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
def test_48_boundaries_classify_without_promoting_mirrors_or_initial_list():
 i=fixture();old=copy.deepcopy(i);v=pre_rule_membership_view(i);assert i==old
 assert(v['total'],v['warning_removed'],v['terminal_entry'],v['delisted'])==(48,37,10,1)
 assert(v['files'],v['pages'],v['official_body_files'],v['mirror_files'])==(48,147,43,5)
 assert(v['explicit_5_to_10'],v['post_rule_removed'],v['date_conflicts'])==(28,12,1)
 assert(v['catalog_companies'],v['catalog_rows'],v['catalog_pages'])==(48,2542,84)
 assert all(r['matches_provider_boundary']for r in v['rows'])and'期初全名单'in v['boundary']

def test_zhongji_exit_and_reentry_are_different_episodes():
 v=pre_rule_membership_view(fixture());r=next(r for r in v['rows']if r['symbol']=='000972');assert r['kind']=='warning_removed'and r['effective_on']=='2026-06-29'and r['post_name']=='中基健康'and r['member_days']==37

def test_terminal_entry_is_not_actual_delisting_and_wanfang_is_not_terminal_start():
 v=pre_rule_membership_view(fixture());r={r['symbol']:r for r in v['rows']};assert r['000638']['kind']=='delisted'and r['000638']['effective_on']=='2026-06-03';assert r['000004']['kind']=='terminal_entry'and r['000004']['effective_on']=='2026-06-23'
 assert r['600608']['date_conflict']and r['600608']['metadata_published_on']=='2026-06-07'and r['600608']['document_dated_on']=='2026-06-08'
 assert r['600777']['source']['host_is_official']is False and r['600777']['verification_level']=='exchange_catalog_plus_pdf_mirror'

@pytest.mark.parametrize('bad',['packet','scope','page','count','symbol','date','last_member','name_st','post_name','mirror','host','hidden_conflict','dated','band','kind','source_set'])
def test_source_date_scope_or_confidence_corruption_does_not_receive_support(bad):
 i=fixture();p=i['pre_rule_membership'];r=next(r for r in p['rows']if r['symbol']=='000972');s=next(s for s in p['sources']if s['announcement_id']==r['source_id'])
 if bad=='packet':r['name']+='changed'
 elif bad=='scope':i['through']='2026-11-05'
 elif bad=='page':s['selected_pages']['1']+='changed'
 elif bad=='count':p['rows'].pop()
 elif bad=='symbol':r['symbol']='000971'
 elif bad=='date':r['effective_on']='2026-06-26'
 elif bad=='last_member':r['last_provider_member']='2026-06-25'
 elif bad=='name_st':r['post_name']='ST中基'
 elif bad=='post_name':r['post_name']='无原文名称'
 elif bad=='mirror':next(r for r in p['rows']if r['symbol']=='600777')['verification_level']='official_body'
 elif bad=='host':s['url']='https://example.com/notice.pdf'
 elif bad=='hidden_conflict':next(r for r in p['rows']if r['symbol']=='600608')['date_conflict']=False
 elif bad=='dated':r['document_dated_on']='2026-06-29'
 elif bad=='band':r['band_excerpt']='涨跌幅由5%变为10%伪造'
 elif bad=='kind':r['kind']='unknown'
 elif bad=='source_set':p['sources'].append(copy.deepcopy(s))
 if bad not in ('packet','scope'):seal(i)
 with pytest.raises((ValueError,KeyError)):pre_rule_membership_view(i)

def test_temporary_event_prices_extend_47_issuers_without_overwriting_156_old_series():
 i=fixture();old=copy.deepcopy(i);j=boundary_price_inputs(i);assert i==old
 assert len({r['symbol']for r in j['fixed_prices']})==203 and len(j['fixed_prices'])-len(i['fixed_prices'])==47*126
 assert j['fixed_prices'][:len(i['fixed_prices'])]==i['fixed_prices']
 assert any(r['symbol']=='000518'and r['has_trade']for r in j['fixed_prices'])

def test_legacy_has_no_invented_boundaries():assert pre_rule_membership_view({})is None
