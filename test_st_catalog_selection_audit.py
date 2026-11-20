from copy import deepcopy
import pytest
from st_catalog_selection_audit import audit_catalog_selection,selected_ids

def row(aid='1225654047',symbol='603959',title='关于收到《现金赠与协议》项下赠与款的公告'):
 return {'announcementId':aid,'secCode':symbol,'secName':'ST百利','announcementTitle':title,'adjunctUrl':'finalpage/2026-11-03/'+aid+'.PDF'}
def page(n,rows,total=2,more=False,query='q',symbol='603959'):
 return {'query_id':query,'symbol':symbol,'page_number':n,'sha256':'a'*64,'locator':f'{query}-{n}.json','payload':{'announcements':rows,'totalAnnouncement':total,'hasMore':more,'totalpages':1}}
def audit(pages,selected=()):return audit_catalog_selection(pages,set(selected),fixed_symbols={'603959'},protected_ids={'1225654047'})

def test_complete_saved_query_uses_terminal_flag_unique_ids_and_total_not_floor_like_page_field():
 result=audit([page(1,[row()],more=True),page(2,[row('2',title='年度报告')])])
 assert result['counts']['pagination_complete_queries']==1
 assert result['counts']['unique_catalog_announcements']==2
 assert len(result['candidates'])==1
 assert result['candidates'][0]['protected_id'] is True
 assert result['candidates'][0]['body_status']=='not_evaluated_by_this_audit'
 assert result['candidates'][0]['classification']=='title_lead_not_confirmed_omission'

@pytest.mark.parametrize('kind,error',[('gap','missing_or_duplicate_page'),('duplicate_page','missing_or_duplicate_page'),('count','row_count_mismatch'),('nonterminal','has_more_not_settled'),('subject','subject_mismatch'),('duplicate_id','duplicate_announcement'),('malformed_total','inconsistent_total')])
def test_incomplete_or_conflicted_query_does_not_silently_become_a_clean_no_omission_result(kind,error):
 pages=[page(1,[row()],more=True),page(2,[row('2',title='年度报告')])]
 if kind=='gap':pages[1]['page_number']=3
 if kind=='duplicate_page':pages[1]['page_number']=1
 if kind=='count':
  for p in pages:p['payload']['totalAnnouncement']=3
 if kind=='nonterminal':pages[1]['payload']['hasMore']=True
 if kind=='subject':pages[1]['payload']['announcements'][0]['secCode']='000001'
 if kind=='duplicate_id':pages[1]['payload']['announcements'][0]['announcementId']='1225654047'
 if kind=='malformed_total':pages[1]['payload']['totalAnnouncement']=[]
 result=audit(pages)
 assert result['queries'][0]['status']=='unverified'
 assert error in result['queries'][0]['errors']
 assert result['candidates']==[]
 assert result['counts']['fixed_symbols_without_complete_saved_query']==1

def test_actual_source_descriptor_excludes_selected_notice_but_metadata_only_does_not_claim_reading():
 assert selected_ids({'metadata':{'announcement_id':'1225654047'}})==set()
 assert selected_ids({'announcement_id':'1225654047','sha256':'not-a-file-hash'})==set()
 ids=selected_ids({'source':{'announcement_id':'1225654047','sha256':'a'*64}})
 assert audit([page(1,[row()],total=1)],ids)['candidates']==[]
 assert len(audit([page(1,[row()],total=1)])['candidates'])==1

def test_supporting_document_is_labeled_without_becoming_independent_case():
 result=audit([page(1,[row(title='关于终止投资交易的核查意见')],total=1)])
 assert result['candidates'][0]['supporting_document_title'] is True
 assert result['counts']['unselected_primary_title_leads']==0
 assert result['counts']['unselected_supporting_title_leads']==1

def test_subject_outside_fixed_scope_is_not_counted_as_coverage():
 result=audit([page(1,[row(symbol='000001')],total=1,symbol='000001')])
 assert result['counts']['symbols_with_complete_saved_queries']==0
 assert 'outside_fixed_scope' in result['queries'][0]['errors']

def test_cross_query_identity_conflict_is_reported_and_not_shown_as_a_clean_candidate():
 result=audit([page(1,[row()],total=1),page(1,[row(title='不同标题')],total=1,query='other')])
 assert result['identity_conflicts']==['1225654047']
 assert result['candidates']==[]

def test_html_title_and_given_catalog_url_are_preserved_as_a_metadata_lead():
 result=audit([page(1,[row(title='关于<em>收到</em>赠与款&nbsp;的公告')],total=1)])
 c=result['candidates'][0]
 assert c['title']=='关于收到赠与款的公告'
 assert c['url']=='https://static.cninfo.com.cn/finalpage/2026-11-03/1225654047.PDF'
 assert c['published_on']=='2026-11-03'

def test_cli_exports_auditable_result_without_network_or_state_writes(tmp_path):
 import json
 from st_catalog_selection_audit import main
 inputs={'captures':[page(1,[row()],total=1)],'selected':[],'fixed':['603959']}
 for name,value in inputs.items():(tmp_path/(name+'.json')).write_text(json.dumps(value))
 output=tmp_path/'audit.json'
 code=main(['--captures',str(tmp_path/'captures.json'),'--selected-ids',str(tmp_path/'selected.json'),'--fixed-symbols',str(tmp_path/'fixed.json'),'--output',str(output)])
 assert code==0
 result=json.loads(output.read_text())
 assert result['counts']['unselected_title_leads']==1
 assert result['candidates'][0]['body_status']=='not_evaluated_by_this_audit'

def test_cli_returns_nonzero_for_unverified_query_instead_of_clean_zero(tmp_path):
 import json
 from st_catalog_selection_audit import main
 for name,value in {'captures':[page(1,[row()],total=2)],'selected':[],'fixed':['603959']}.items():(tmp_path/(name+'.json')).write_text(json.dumps(value))
 assert main(['--captures',str(tmp_path/'captures.json'),'--selected-ids',str(tmp_path/'selected.json'),'--fixed-symbols',str(tmp_path/'fixed.json'),'--output',str(tmp_path/'audit.json')])==2
