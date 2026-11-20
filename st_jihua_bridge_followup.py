"""Partial numerical correspondence is not a complete accounting reconciliation."""
from copy import deepcopy
from decimal import Decimal as D
import re
from canonical_json import digest

def jihua_bridge_followup(inputs, prior):
    packet=inputs.get('jihua_bridge_followup')
    if packet is None:return None
    if packet.get('version')!=1 or packet.get('content_digest')!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('jihua packet changed')
    if digest(prior)!=PRIOR_DIGEST or digest(inputs['twentysecond_period_followup'])!=SCOPE_DIGEST:raise ValueError('jihua prior source scope changed')
    result=packet['result']
    if digest(result)!=VIEW_DIGEST:raise ValueError('jihua result changed')
    sources={s['announcement_id']:s for s in inputs['twentysecond_period_followup']['sources']}
    norm=lambda x:re.sub(r'[\s,]','',x)
    for row in result['rows']:
        delta=D(row['nine_month_reported'])-D(row['h1_original'])-D(row['q3_direct'])
        if delta!=D(row['difference']) or D(row['implied_comparable_h1'])!=D(row['nine_month_reported'])-D(row['q3_direct'])or row['implied_is_disclosed_h1']:raise ValueError('jihua quarter bridge changed')
        if row['h1_original']not in norm(sources['1225493692']['selected_pages']['5'])or not all(x in norm(sources['1225644670']['selected_pages']['2'])for x in [row['nine_month_reported'],row['q3_direct']]):raise ValueError('jihua financial source changed')
    n=result['nonrec_bridge']
    if D(n['nine_month_reported'])-D(n['h1_original'])-D(n['q3_direct'])!=D('-100.00')or n['derived_minus_direct']!='-100.00':raise ValueError('jihua nonrec residual changed')
    if result['rows'][1]['difference']!=result['same_control_premerge_profit'] or '38852.53'not in norm(sources['1225644670']['selected_pages']['10']):raise ValueError('jihua premerge clue changed')
    if result['full_reconciliation_verified']or result['method_promotions']:raise ValueError('jihua unsupported reconciliation')
    return deepcopy(result)

PRIOR_DIGEST='2a0ce131a5ef27c18b9eb83ef1a92063e752a2a9bebf9f99fb50e7090cc17844'
SCOPE_DIGEST='1e920ab6e6d23dcb0e5550bc3fea535050967e2b0f42f8fc69e46f39543a8cfc'
VIEW_DIGEST='9cd8d66281ef4c54e6aeb08298f2194036e68e751e1a38e4a1e11325f063d853'
