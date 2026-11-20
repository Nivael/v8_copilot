"""Versioned title-rule extension; preserves v1 and never promotes title leads to facts."""
import re
from st_catalog_selection_audit import audit_catalog_selection,_title
RESOLUTION_RULE=r'资金占用.*(解决完毕|解决完成|整改完毕|整改完成|全部解决|全部收回|清理完毕)'
VERSION='saved_catalog_resolution_audit_v2'

def audit_resolution(captures,selected,*,fixed_symbols,protected_ids=()):
    base=audit_catalog_selection(captures,selected,fixed_symbols=fixed_symbols,protected_ids=protected_ids)
    complete={(q['query_id'],q['symbol']) for q in base['queries'] if q['status']=='saved_pagination_complete'}
    rows={};conflicts=set(base['identity_conflicts']);protected=set(protected_ids)
    for c in captures:
        if (c['query_id'],c['symbol'])not in complete:continue
        for a in c['payload']['announcements']:
            aid=str(a['announcementId']);title=_title(a['announcementTitle']);path=str(a.get('adjunctUrl',''))
            day=re.search(r'finalpage/(\d{4}-\d{2}-\d{2})/',path)
            row={'announcement_id':aid,'symbol':c['symbol'],'title':title,'url':path if path.startswith('https://')else'https://static.cninfo.com.cn/'+path,'published_on':day[1] if day else None,'catalog_query':c['query_id'],'catalog_page':c['page_number'],'catalog_sha256':c['sha256']}
            if aid in rows and any(row[k]!=rows[aid][k]for k in ('symbol','title','url','published_on')):conflicts.add(aid)
            rows[aid]=row
    old_matches={r['announcement_id']for r in audit_catalog_selection(captures,set(),fixed_symbols=fixed_symbols)['candidates']}
    extension=[]
    for aid,r in sorted(rows.items()):
        if aid in conflicts or aid in old_matches or not re.search(RESOLUTION_RULE,r['title']):continue
        extension.append({**r,'rule':'occupation_resolution_v2','selected_source_identity_present':aid in selected,'protected_id':aid in protected,'body_status':'selected_identity_not_body_certification'if aid in selected else'title_only_pending_body_review','classification':'title_lead_not_confirmed_fact'})
    return {'version':VERSION,'rule':RESOLUTION_RULE,'base_counts':base['counts'],'identity_conflicts':sorted(conflicts),'unverified_queries':[q for q in base['queries']if q['status']!='saved_pagination_complete'],'new_title_matches':extension,'new_unselected_title_leads':[r for r in extension if not r['selected_source_identity_present']],'v1_unselected_title_leads':base['candidates'],'boundary':'Additional title matches only; no new independent cases, repayment facts or completeness guarantee.'}
