"""Bounded literal-fact checks; deliberately not certification of full taxonomy semantics."""
from datetime import datetime, timezone
import json

import pytest
from pydantic import ValidationError

from api_contract import ResearchRequest
from api_contract_v2 import NarrativeStatement, NarrativeStep, ResearchNarrative
from discipline_backing import unsupported_discipline_clauses
from evidence_gateway import (DecisionAudit, DecisionFactor, ExternalEvidenceInput, ResearchDraft,
                              augment_evidence_pack, build_evidence_pack, validate_research_draft)
from llm.composer import NarrativeComposer, _validated_statement
from llm.providers import FakeLLMProvider
from llm.schemas import StructuredNarrativeStatement

URL = 'https://www.szse.cn/disclosure/supervision/participant/t20240514_607222.html'
COMPANY = '华西证券股份有限公司受到公开谴责。'
PERSON = '郑义受到通报批评。'


def summary(value, **extra):
    return json.dumps({'fact':value,'source_kind':'official_exchange_or_regulator','source_url':URL,**extra},ensure_ascii=False)


@pytest.fixture
def pack():
    local = build_evidence_pack(ResearchRequest(question='纪律处分类型和对象应当怎样核对？',llm_mode='off'))
    external = ExternalEvidenceInput(source_kind='official_exchange_or_regulator',source_mode='live_web_observation',
        subject_ref='华西证券及相关当事人',title='关于对华西证券股份有限公司及相关当事人给予纪律处分的决定',source_url=URL,
        published_at='2024-05-14',fetched_at=datetime.now(timezone.utc).isoformat(),
        coverage_note='仅核对该文书明确列明的对象与对应类型，不推断后续资本运作。',
        facts=[{'fact_id':'company','text':COMPANY},{'fact_id':'person','text':PERSON}])
    return augment_evidence_pack(local,[external])


def backings(pack):
    identifier=pack.external_evidence[0].evidence_id
    return [{'kind':'provenance_ref','ref':f'{identifier}:{key}'} for key in ('company','person')]


def draft(pack,text):
    return ResearchDraft(narrative=ResearchNarrative(direct_answer=NarrativeStatement(text=text,backing=backings(pack)),
        basis_note='正式原文事实核对，不证明完整语义或后续审批条件。'))


@pytest.mark.parametrize('text',[ '华西证券股份有限公司受到通报批评。','郑义受到公开谴责。',
    '华西证券股份有限公司并未受到公开谴责。','华西证券股份有限公司受到监管警示。',
    COMPANY+'此后公司已经完成发行股份。',COMPANY+'所以当前具备发行股份审批条件。'])
def test_workbench_rejects_pooled_words_reassigned_actors_negation_and_invented_followup(pack,text):
    result=validate_research_draft(pack,draft(pack,text))
    assert not result.valid and 'unsupported_discipline_attribution' in {issue.code for issue in result.issues}


def test_exact_separate_facts_pass_and_validation_does_not_modify_the_pack(pack):
    before=pack.model_dump_json()
    result=validate_research_draft(pack,draft(pack,COMPANY+PERSON))
    assert result.valid and before==pack.model_dump_json()
    wrong=draft(pack,'华西证券股份有限公司受到通报批评。')
    assert not validate_research_draft(pack,wrong).valid


def test_discipline_assertions_in_titles_and_decision_audits_cannot_hide_behind_correct_body(pack):
    value=draft(pack,COMPANY)
    value.narrative.reasoning_steps=[NarrativeStep(title='公司受到通报批评',text=COMPANY,backing=backings(pack))]
    assert not validate_research_draft(pack,value).valid
    value.narrative.reasoning_steps=[]
    value.decision_audit=DecisionAudit(judgment=COMPANY,judgment_backing=backings(pack),confidence='low',
        factors=[DecisionFactor(factor_id='actors',label='公司受到通报批评',direction='limits',importance='high',rationale=COMPANY,backing=backings(pack))])
    assert not validate_research_draft(pack,value).valid
    value.decision_audit.factors[0].label='可以买入'
    assert 'forbidden_wording' in {issue.code for issue in validate_research_draft(pack,value).issues}


def test_quotes_cannot_drop_a_later_qualification_or_negation():
    facts=[summary('公司受到公开谴责。以上为拟作出的决定，尚未生效。')]
    assert unsupported_discipline_clauses('公司受到公开谴责。',facts)
    assert not unsupported_discipline_clauses('公司受到公开谴责。以上为拟作出的决定，尚未生效。',facts)
    assert unsupported_discipline_clauses('公司受到公开谴责。',[summary('公司并未受到公开谴责。')])


def test_present_dates_do_not_authorize_a_new_order_or_financing_instrument():
    facts=[summary('公司于2020-01-02受到公开谴责。'),summary('公司于2020-01-01披露现金收购预案。')]
    assert unsupported_discipline_clauses('公司于2020-01-02受到公开谴责。此后公司于2020-01-01披露现金收购预案。',facts)
    assert unsupported_discipline_clauses('公司于2020-01-02受到公开谴责。公司于2020-01-01披露发行股份预案。',facts)
    assert unsupported_discipline_clauses('公司受到公 开谴责。',[summary('其他事实。')])
    assert unsupported_discipline_clauses(COMPANY,[summary('没有核读正文。',title=COMPANY)])


@pytest.mark.parametrize('override',[{'source_kind':'market_data_provider'},{'source_url':'https://example.invalid/szse'},
    {'source_url':'https://www.szse.cn.example.invalid/a'},{'source_url':123},
    {'source_url':'https://user:password@www.szse.cn/a'},{'fact':None}])
def test_source_metadata_titles_and_unknown_hosts_are_not_official_facts(override):
    assert unsupported_discipline_clauses(COMPANY,[summary(COMPANY,**override)])


def test_only_actually_cited_facts_can_support_a_statement(pack):
    value=draft(pack,PERSON)
    value.narrative.direct_answer.backing=value.narrative.direct_answer.backing[:1]
    assert not validate_research_draft(pack,value).valid
    assert not unsupported_discipline_clauses('不讨论此主题。',[summary('别的事实。')])
    assert not unsupported_discipline_clauses('公开谴责',[summary(COMPANY)],title=True)


def test_composer_statement_path_applies_the_same_gate():
    key=('provenance_ref','official')
    statement=StructuredNarrativeStatement(text=COMPANY,backing=[{'kind':key[0],'ref':key[1]}])
    assert _validated_statement(statement,{key:summary(COMPANY)}).text==COMPANY
    statement.text='华西证券股份有限公司受到通报批评。'
    with pytest.raises(ValidationError,match='不能拼接对象'):
        _validated_statement(statement,{key:summary(COMPANY)})


def test_legacy_composer_drops_unsupported_claim_in_its_real_compose_path():
    from answer_engine import AnswerCard
    import answer_engine
    card=answer_engine.card_stock_comparison(['603398','300067'],'沐邦和南都怎么比较？')
    assert isinstance(card,AnswerCard)
    from dataclasses import replace
    row={'row_id':'official','fact':COMPANY,'source_kind':'official_exchange_or_regulator','source_url':URL}
    card=replace(card,body_rows=[row],analysis_claims=[])
    provider=FakeLLMProvider(response_factory=lambda *_:{'claims':[{'text':'华西证券股份有限公司受到通报批评。',
        'claim_type':'fact','backing':{'kind':'query_row','ref':'official'}}]})
    result=NarrativeComposer(provider=provider,model='fake').compose(card)
    assert result.accepted_claims==[] and len(result.rejected_claims)==1
    assert '未逐条匹配' in result.rejected_claims[0].reason
