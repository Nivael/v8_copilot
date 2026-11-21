from st_catalog_resolution_audit import audit_resolution
from st_catalog_selection_audit import audit_catalog_selection

def capture(title,aid='1'):
 return {'query_id':'q','symbol':'000826','page_number':1,'sha256':'a'*64,'locator':'saved.json','payload':{'totalAnnouncement':1,'hasMore':False,'announcements':[{'secCode':'000826','announcementId':aid,'announcementTitle':title,'adjunctUrl':'finalpage/2026-08-26/'+aid+'.PDF'}]}}
def test_new_wording_is_only_a_title_lead_and_v1_is_preserved():
 caps=[capture('关于资金占用事项解决完毕的公告')]
 assert audit_catalog_selection(caps,set(),fixed_symbols={'000826'})['counts']['matched_titles']==0
 r=audit_resolution(caps,set(),fixed_symbols={'000826'});assert len(r['new_unselected_title_leads'])==1
 assert r['new_unselected_title_leads'][0]['body_status']=='title_only_pending_body_review'
def test_selected_identity_is_not_certified_body_or_new_case():
 r=audit_resolution([capture('资金占用整改完成公告')],{'1'},fixed_symbols={'000826'},protected_ids={'1'})
 assert not r['new_unselected_title_leads'];assert r['new_title_matches'][0]['protected_id']
 assert r['new_title_matches'][0]['body_status']=='selected_identity_not_body_certification'
def test_incomplete_pages_and_nonresolution_titles_do_not_become_new_leads():
 c=capture('关于资金占用事项解决完毕的公告');c['payload']['hasMore']=True
 r=audit_resolution([c],set(),fixed_symbols={'000826'});assert r['unverified_queries'];assert not r['new_title_matches']
 assert not audit_resolution([capture('关于资金占用事项进展的公告')],set(),fixed_symbols={'000826'})['new_title_matches']
def test_old_rule_match_is_not_double_counted_as_extension():
 r=audit_resolution([capture('资金占用清偿及解决完毕公告')],set(),fixed_symbols={'000826'})
 assert len(r['v1_unselected_title_leads'])==1;assert not r['new_title_matches']
