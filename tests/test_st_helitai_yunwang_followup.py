import gzip,json
from pathlib import Path
from hashlib import sha256
import pytest
from canonical_json import digest
from st_helitai_yunwang_followup import followup_view,freeze_audit,FREEZE_ROWS

def fixture():return json.loads(gzip.decompress(Path('tests/fixtures/st-helitai-yunwang-followup.json.gz').read_bytes()))
def run(x):return followup_view(x,x['test_prior'],x['test_current'])
def test_freeze_conflict_is_reproduced_without_selecting_a_true_total_or_loss():
 r=freeze_audit(FREEZE_ROWS,'9320369.50');assert r['row_sum_yuan']=='11475904.50'and r['difference_yuan']=='2155535.00';assert r['parent_only_sum_yuan']==r['reported_subtotal_yuan'];assert r['certified_total_yuan']is None and r['unresolved']and r['not_loss']
def test_cases_reopen_independently_and_repeated_penalty_notices_do_not_add_repairs():
 r=run(fixture());assert r['counts']==dict(files=8,pages=21,viewed_pages=21,chains=7,complete_windows=10,unfinished_windows=2,initial_coverage=66)
 chains={c['key']:c for c in r['chains']};assert '重新起诉'in chains['lead_intelligent']['changes'][-1]['state'];assert '对应账户待办'in chains['rent']['changes'][-1]['state'];assert '不认证已实际划款'in chains['construction']['changes'][-1]['state'];assert '不当已清偿'in chains['convertible_loan']['changes'][0]['state'];assert len(r['helitai_updates'])==4 and all(u['independent_remediation_added']==0 for u in r['helitai_updates']);assert r['method_promotions']==0
@pytest.mark.parametrize('mutation',['digest','prior','market','current','source_sha','source_date','source_url','page','stage','freeze_amount','freeze_entity','subtotal'])
def test_rejects_source_stage_and_amount_scope_mutations(mutation):
 x=fixture();p=x['helitai_yunwang_followup'];s=p['sources'][0]
 if mutation=='digest':p['content_digest']='bad'
 elif mutation=='prior':p['prior_digest']='bad'
 elif mutation=='market':p['market_digest']='bad'
 elif mutation=='current':p['current_digest']='bad'
 elif mutation=='source_sha':s['sha256']='bad'
 elif mutation=='source_date':s['published_on']='2026-07-03'
 elif mutation=='source_url':s['url']='https://example.com/'
 elif mutation=='page':s['selected_pages']['1']+='forged'
 elif mutation=='stage':
  s=next(s for s in p['sources']if s['announcement_id']=='1225669041');s['selected_pages']['2']=s['selected_pages']['2'].replace('申请执行','已执行完毕');s['page_hashes'][1]=sha256(s['selected_pages']['2'].encode()).hexdigest()
 elif mutation=='freeze_amount':p['freeze_rows'][0]['amount']='0'
 elif mutation=='freeze_entity':p['freeze_rows'][-1]['entity']='listed_company'
 elif mutation=='subtotal':p['reported_subtotal_yuan']='11475904.50'
 if mutation!='digest':p['content_digest']=digest({k:v for k,v in p.items()if k!='content_digest'})
 with pytest.raises((ValueError,KeyError)):run(x)
def test_missing_packet_is_optional():assert followup_view({},None,None)is None
