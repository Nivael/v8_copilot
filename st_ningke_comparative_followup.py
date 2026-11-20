"""Cross-file corroboration does not silently amend an unresolved original report."""
from copy import deepcopy
from decimal import Decimal as D
import re
from canonical_json import digest

def ningke_comparative_followup(inputs, prior):
    packet=inputs.get('ningke_comparative_followup')
    if packet is None:return None
    if packet.get('version')!=1 or packet.get('content_digest')!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('ningke comparative packet changed')
    if digest(prior)!=PRIOR_DIGEST:raise ValueError('ningke comparative prior changed')
    sources={s['announcement_id']:s for key in ['initial_fourteenth_four','fourteenth_period_followup']for s in inputs[key]['sources']if s['announcement_id']in ['1225172303','1225530042','1225650652']}
    if digest(sources)!=SOURCE_DIGEST:raise ValueError('ningke comparative sources changed')
    result=packet['result']
    if digest(result)!=VIEW_DIGEST:raise ValueError('ningke comparative reading changed')
    a=result['values']['annual_2025']
    if D(a['assets'])-D(a['liabilities'])!=D(a['total_equity'])or D(a['parent_equity'])+D(a['minority_equity'])!=D(a['total_equity']):raise ValueError('ningke annual identity changed')
    norm=lambda s:re.sub(r'[\s,]','',s)
    for row in result['comparison_rows']:
        metric=row['metric'];base=D(a[metric]);current=D(row['h1_current']);summary=D(row['h1_summary_prior'])
        if not row['audited_2025']==row['h1_balance_prior']==row['q3_prior']==a[metric]:raise ValueError('ningke comparable period changed')
        if row['h1_summary_prior']in [a[metric],result['values']['annual_2024'][metric]]:raise ValueError('ningke unsupported year shift')
        if D(row['change_using_summary'])!=current-summary or D(row['change_using_corroborated_balance'])!=current-base or D(row['recomputed_change_pct'])!=(current/base-1)*100:raise ValueError('ningke comparative calculation changed')
        if row['h1_summary_prior']not in norm(sources['1225530042']['selected_pages']['6'])or row['q3_prior']not in norm(sources['1225650652']['selected_pages']['1']):raise ValueError('ningke source row changed')
    if D(result['comparison_rows'][1]['change_using_corroborated_balance'])!=D('-132468807.22'):raise ValueError('ningke h1 equity bridge changed')
    if result['h1_summary_conflict_resolved']or result['simple_2024_year_shift_supported']or result['method_promotions']:raise ValueError('ningke unsupported closure')
    return deepcopy(result)

PRIOR_DIGEST='adf959753381464fbd1d42b494452b79a2afb56a593856d8e2d888c074879fe3'
SOURCE_DIGEST='94d1aba6586f1cdd581efb3835f15dbbd48687ab256bed342a4057f3b0dad218'
VIEW_DIGEST='eb533288b8e394ec9bccfa5f0dd90326acd26c4ddf4b821e303fbf8333382cfe'
