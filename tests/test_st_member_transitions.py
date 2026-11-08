from copy import deepcopy
import pytest
from canonical_json import digest
from st_member_transitions import membership_scope_digest,member_transition_view


def fixture():
    inputs={'calendar':['2026-07-03','2026-07-06','2026-07-07','2026-11-06'],'through':'2026-11-06','members':[{'symbol':'000711','trade_date':d} for d in ['2026-07-03','2026-07-06']]}
    source={'sha256':'a'*64,'title':'撤销其他风险警示原公告','url':'https://example.com/original.pdf#page=1','page':1}
    row={'symbol':'000711','anchor_name':'ST京蓝','new_name':'京蓝科技','status':'warning_removed','warning_removed':'other','announced_on':'2026-07-06','effective_on':'2026-07-07','provider_last_st':'2026-07-06','provider_first_absent':'2026-07-07','facts':[{'published_on':'2026-07-06','text':'撤销警示','source':source}]}
    packet={'anchor':'2026-07-03','through':inputs['through'],'membership_scope_digest':membership_scope_digest(inputs),'rows':[row]};packet['content_digest']=digest(packet);inputs['member_transitions']=packet
    return inputs


def resign(i):
    p=i['member_transitions'];p['content_digest']=digest({k:v for k,v in p.items() if k!='content_digest'})


def test_counts_and_actual_boundary_are_derived_without_removing_fixed_members():
    inputs=fixture();before=deepcopy(inputs['members']);v=member_transition_view(inputs)
    assert v['total']==1 and v['counts']=={'warning_removed':1}
    assert v['matching_boundaries']==1 and inputs['members']==before


def test_announcement_date_does_not_replace_effective_date_and_conflict_is_visible():
    i=fixture();row=i['member_transitions']['rows'][0];row['effective_on']='2026-07-06';resign(i)
    v=member_transition_view(i)
    assert not v['rows'][0]['effective_matches_membership'] and v['matching_boundaries']==0


def test_packet_and_member_scope_are_bound():
    i=fixture();i['member_transitions']['rows'][0]['new_name']='invented'
    with pytest.raises(ValueError,match='packet'):member_transition_view(i)
    i=fixture();i['members'].append({'symbol':'000711','trade_date':'2026-07-07'})
    with pytest.raises(ValueError,match='membership binding'):member_transition_view(i)
    i['member_transitions']['membership_scope_digest']=membership_scope_digest(i);resign(i)
    with pytest.raises(ValueError,match='dates changed'):member_transition_view(i)


def test_future_sources_unknown_stages_and_missing_exits_fail_closed():
    for mutation in ['future','unknown','missing','duplicate']:
        i=fixture();row=i['member_transitions']['rows'][0]
        if mutation=='future':row['facts'][0]['published_on']='2026-11-07'
        elif mutation=='unknown':row['status']='all_risks_gone'
        elif mutation=='missing':i['member_transitions']['rows']=[]
        else:i['member_transitions']['rows'].append(deepcopy(row))
        resign(i)
        with pytest.raises(ValueError):member_transition_view(i)


def test_explicit_approval_date_cannot_be_fabricated_after_announcement():
    i=fixture();i['member_transitions']['rows'][0]['approval_on']='2026-07-07';resign(i)
    with pytest.raises(ValueError,match='approval date'):member_transition_view(i)
