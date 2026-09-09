"""The host can decompose a multi-company research task without an API crash."""
import pytest
from api_contract import ResearchObject, ResearchRequest
from deterministic_router import route_question
from evidence_gateway import build_evidence_pack

@pytest.mark.parametrize('ref', ['comparison:603398,002157,002713', 'comparison:603398', 'comparison:603398,603398', 'comparison:'])
def test_unsupported_comparison_does_not_execute(ref):
    route = route_question({'user_question': '比较公开公告和股价走势', 'object': {'kind': 'cohort', 'ref': ref}})
    assert route.predicted_route == 'clarify'
    assert route.matched_rules == ['comparison_scope_requires_decomposition']

def test_three_company_question_builds_pack_instead_of_crashing():
    pack = build_evidence_pack(ResearchRequest(question='研究沐邦，参考正邦出投资人后的法院受理与东易股价走势', llm_mode='off'))
    assert pack.question_scope['route'] == 'clarify'
    assert set(pack.question_scope['object']['ref'].removeprefix('comparison:').split(',')) == {'603398', '002157', '002713'}

def test_two_company_comparison_route_unchanged():
    route = route_question({'user_question': '比较公开公告', 'object': {'kind': 'cohort', 'ref': 'comparison:603398,002157'}})
    assert route.predicted_route == 'answer_query'
