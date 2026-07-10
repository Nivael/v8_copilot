from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm.composer import NarrativeComposer, minimal_composer_payload
from llm.integration import OpenAIInterpretationProvider, OpenAINarrativeProvider
from llm.models import ClaimBatch
from llm.parser import QuestionParser
from llm.providers import FakeLLMProvider, OpenAIResponsesProvider, ProviderUnavailable
from run_seeds import write_seed_cards
from contracts.v8_copilot_api_contract_v0.models import ResearchRequest
from service.orchestrator import ResearchOrchestrator


ROOT = Path(__file__).resolve().parents[1]


def test_parser_payload_is_question_and_context_only() -> None:
    parsed = QuestionParser(FakeLLMProvider()).parse(
        "603398 为什么 ST？",
        {"symbol": "603398", "event_id": "announcement:1"},
    )
    assert parsed.interpretation.object_ref == "603398"
    assert parsed.route.predicted_route == "answer_query"
    assert "facts" not in type(parsed.interpretation).model_fields


def test_deterministic_boundary_overrules_interpretation() -> None:
    parsed = QuestionParser(FakeLLMProvider()).parse(
        "603398 能买吗？",
        {"symbol": "603398"},
    )
    assert parsed.route.predicted_route == "refuse_or_rewrite"


def test_composer_validates_all_seven_seed_cards(tmp_path: Path) -> None:
    cards = write_seed_cards(tmp_path)
    composer = NarrativeComposer(FakeLLMProvider())
    for card in cards.values():
        claims = composer.compose(card)
        assert claims
        assert all(claim["backing"]["ref"] for claim in claims)


def test_composer_rejects_unbacked_claim(tmp_path: Path) -> None:
    card = next(iter(write_seed_cards(tmp_path).values()))

    class BadProvider:
        provider_name = "bad"

        def parse(self, **_: object) -> ClaimBatch:
            return ClaimBatch.model_validate({
                "claims": [{
                    "text": "没有来源的结论。",
                    "claim_type": "fact",
                    "backing": {"kind": "query_row", "ref": "missing"},
                }]
            })

    with pytest.raises(ValueError, match="backing 无对应对象"):
        NarrativeComposer(BadProvider()).compose(card)


def test_minimal_payload_excludes_versions_and_freshness(tmp_path: Path) -> None:
    card = next(iter(write_seed_cards(tmp_path).values()))
    payload = minimal_composer_payload(card)
    assert "source_freshness" not in payload
    assert "v7_release_library_version" not in payload
    assert "data_snapshot_as_of" not in payload
    assert set(payload) <= {
        "question", "object_ref", "view", "as_of", "sample_scope", "evidence_grade",
        "lens_invocations", "lens_gap", "body_rows", "existing_claims", "data_debt",
        "data_debt_refs", "caveats", "provenance", "backing_catalog",
    }


def test_openai_provider_requires_explicit_key_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("V8_OPENAI_MODEL", raising=False)
    with pytest.raises(ProviderUnavailable, match="OPENAI_API_KEY"):
        OpenAIResponsesProvider()
    with pytest.raises(ProviderUnavailable, match="V8_OPENAI_MODEL"):
        OpenAIResponsesProvider(api_key="test-key")


def test_twenty_paraphrases_have_expected_legal_routes() -> None:
    from evals.deterministic_router_v0 import route_question

    path = ROOT / "evals/question_routing_paraphrases_v0.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 20
    predictions = [route_question(row).predicted_route for row in rows]
    assert predictions == [row["expected_route"] for row in rows]


def test_fake_provider_runs_through_public_orchestrator_contract() -> None:
    provider = FakeLLMProvider()
    orchestrator = ResearchOrchestrator(
        claim_provider=OpenAINarrativeProvider(provider),
        interpretation_provider=OpenAIInterpretationProvider(provider),
    )
    response = orchestrator.answer(ResearchRequest(
        question="重整投资人招募后，下一个公告节点平均多久？",
        object={"kind": "cohort", "ref": "restructuring_investor_recruitment"},
        llm_mode="auto",
    ))

    assert response.status == "complete"
    assert response.interpretation.generated_by == "llm_validated"
    assert response.answer_card is not None
    assert response.claims
