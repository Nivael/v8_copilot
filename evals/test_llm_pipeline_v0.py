from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import llm.config as config_module
from answer_engine import card_calendar_regime_evidence, card_province_mapping_debt
from evals.validate_w2_evals import QUESTION_SET, load_jsonl
from llm.composer import NarrativeComposer, _unsupported_numbers
from llm.parser import QuestionParser
from llm.providers import FakeLLMProvider, LLMProviderError, OpenAIResponsesProvider
from llm.schemas import NarrativeDraft, ParsedQuestion


def _context(symbol: str | None = None) -> dict:
    return {
        "symbol": symbol,
        "date_range": None,
        "selected_event": None,
        "selected_episode": None,
        "selected_lenses": [],
        "active_question": None,
        "answer_card_id": None,
    }


def _parser_payload(payload: dict) -> dict:
    context = payload["research_context"]
    symbol = context.get("symbol")
    return {
        "normalized_question": payload["question"],
        "object_kind": "stock" if symbol else "unknown",
        "object_ref": symbol or "unknown",
        "intent": "research_question",
        "time_range": {"start": "", "end": ""},
        "dimensions": [],
        "ambiguities": [],
        "candidate_topics": [],
        "proposed_route": "lens_gap",
        "compliant_rewrite": "",
    }


def _parser_factory(response_model: type, payload: dict) -> dict:
    assert response_model is ParsedQuestion
    return _parser_payload(payload)


def test_parser_sends_only_question_and_w1_research_context() -> None:
    provider = FakeLLMProvider(response_factory=_parser_factory)
    parser = QuestionParser(provider, model="fake-parser")

    parser.parse(
        "沐邦平台整理期该看哪些窗口？",
        _context("603398"),
        authoritative_object={"kind": "stock", "ref": "603398"},
    )

    call = provider.calls[0]
    assert set(call.payload) == {"question", "research_context"}
    assert set(call.payload["research_context"]) == set(_context())
    serialized = json.dumps(call.payload, ensure_ascii=False)
    assert "body_rows" not in serialized
    assert "release_library" not in serialized
    assert "company_announcements" not in serialized


def test_parser_rejects_pre_contract_context_fields() -> None:
    provider = FakeLLMProvider(response_factory=_parser_factory)

    with pytest.raises(ValueError, match="W1 契约外字段"):
        QuestionParser(provider, model="fake").parse(
            "问题",
            {"object_kind": "stock", "object_ref": "603398"},
        )


def test_authoritative_object_and_router_overrule_llm() -> None:
    provider = FakeLLMProvider(response_factory=_parser_factory)
    result = QuestionParser(provider, model="fake").parse(
        "这票目标价看到多少？",
        _context(),
        authoritative_object={"kind": "stock", "ref": "603398"},
    )

    assert result.interpretation["object"] == {"kind": "stock", "ref": "603398"}
    assert result.adjudicated_route.predicted_route == "refuse_or_rewrite"
    assert result.llm_route_overruled is True
    assert "目标价" not in result.compliant_rewrite
    assert result.route_payload["contract_version"] == "v8_copilot_api_contract_v0"


def test_fake_parser_keeps_30_question_router_baseline() -> None:
    provider = FakeLLMProvider(response_factory=_parser_factory)
    parser = QuestionParser(provider, model="fake")
    failures = []
    for row in load_jsonl(QUESTION_SET):
        obj = row["object"]
        symbol = obj["ref"] if obj["kind"] == "stock" else None
        result = parser.parse(
            row["user_question"],
            _context(symbol),
            authoritative_object=obj,
        )
        actual = result.adjudicated_route.predicted_route
        if actual != row["expected_route"]:
            failures.append((row["question_id"], row["expected_route"], actual))

    assert failures == []
    assert len(provider.calls) == 30


def test_parser_failure_degrades_to_deterministic_route() -> None:
    provider = FakeLLMProvider(responses=[])
    result = QuestionParser(provider, model="fake").parse_or_fallback(
        "这票能买吗？",
        _context("603398"),
        authoritative_object={"kind": "stock", "ref": "603398"},
    )

    assert result.llm_used is False
    assert result.adjudicated_route.predicted_route == "refuse_or_rewrite"
    assert result.compliant_rewrite
    assert result.degraded_reasons == ["LLM 问题解析降级: LLMProviderError"]


def test_missing_model_degrades_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_file = tmp_path / "v8_copilot.env"
    env_file.write_text("OPENAI_API_KEY=fake\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_SECRETS_FILE", env_file)
    monkeypatch.delenv("V8_OPENAI_MODEL", raising=False)
    provider = FakeLLMProvider(response_factory=_parser_factory)

    result = QuestionParser(provider).parse_or_fallback(
        "为什么 ST？",
        _context("603398"),
        authoritative_object={"kind": "stock", "ref": "603398"},
    )

    assert result.llm_used is False
    assert result.degraded_reasons == ["LLM 问题解析降级: LLMConfigurationError"]
    assert provider.calls == []


def test_composer_filters_invalid_forbidden_and_unsupported_numeric_claims() -> None:
    card = card_calendar_regime_evidence()
    row_id = card.body_rows[0]["row_id"]
    provider = FakeLLMProvider(responses=[{
        "claims": [
            {
                "text": "该记录给出了带样本量和反例边界的历史弱先验。",
                "claim_type": "fact",
                "backing": {"kind": "query_row", "ref": row_id},
            },
            {
                "text": "这个引用并不存在。",
                "claim_type": "fact",
                "backing": {"kind": "query_row", "ref": "missing-row"},
            },
            {
                "text": "因此应该买入。",
                "claim_type": "inference",
                "backing": {"kind": "lens_invocation", "ref": "RL-A-001"},
            },
            {
                "text": "该记录包含 999999 个样本。",
                "claim_type": "fact",
                "backing": {"kind": "query_row", "ref": row_id},
            },
        ]
    }])

    result = NarrativeComposer(provider, model="fake-composer").compose(card)
    public_text = json.dumps(result.public_payload(), ensure_ascii=False)

    assert len(result.accepted_claims) == 1
    assert len(result.rejected_claims) == 3
    assert "这个引用并不存在" not in public_text
    assert "因此应该买入" not in public_text
    assert "999999" not in public_text


def test_composer_payload_is_filtered_and_catalogued() -> None:
    card = card_calendar_regime_evidence()
    provider = FakeLLMProvider(responses=[{"claims": []}])

    NarrativeComposer(provider, model="fake").compose(card)

    payload = provider.calls[0].payload
    assert set(payload) == {
        "filtered_answer_card",
        "backing_catalog",
        "evidence_summary",
    }
    filtered = payload["filtered_answer_card"]
    assert "provenance" not in filtered
    assert "source_freshness" not in filtered
    assert "v7_release_library_version" not in filtered
    assert {entry["kind"] for entry in payload["backing_catalog"]} == {
        "query_row",
        "lens_invocation",
        "provenance_ref",
    }


def test_composer_failure_returns_original_valid_card() -> None:
    card = card_calendar_regime_evidence()
    result = NarrativeComposer(FakeLLMProvider(), model="fake").compose_or_fallback(card)

    assert result.llm_used is False
    assert result.answer_card is card
    assert result.accepted_claims == []
    assert result.degraded_reasons == ["LLM 叙述生成降级: LLMProviderError"]
    result.public_payload()


def test_composer_salvages_valid_narrative_when_one_step_fails_backing_gate() -> None:
    card = card_calendar_regime_evidence()
    row_id = card.body_rows[0]["row_id"]
    provider = FakeLLMProvider(responses=[{
        "claims": [],
        "narrative": {
            "direct_answer": {
                "text": "当前记录只支持历史弱先验。",
                "backing": [{"kind": "query_row", "ref": row_id}],
            },
            "reasoning_steps": [{
                "title": "非法数字",
                "text": "这里凭空加入 999999 个样本。",
                "backing": [{"kind": "query_row", "ref": row_id}],
            }, {
                "title": "负数校验",
                "text": "这里又凭空加入 -999999 个样本。",
                "backing": [{"kind": "query_row", "ref": row_id}],
            }, {
                "title": "目标价判断",
                "text": "当前记录只支持历史弱先验。",
                "backing": [{"kind": "query_row", "ref": row_id}],
            }, {
                "title": "中文数量校验",
                "text": "这里凭空加入三个月观察期。",
                "backing": [{"kind": "query_row", "ref": row_id}],
            }],
            "uncertainties": [],
            "watch_items": [],
        },
    }])

    result = NarrativeComposer(provider, model="fake").compose(card)

    assert result.research_narrative is not None
    assert result.research_narrative.direct_answer.text == "当前记录只支持历史弱先验。"
    assert result.research_narrative.reasoning_steps == []
    assert result.degraded_reasons == [
        "LLM 主叙述有 4 个 statement 未通过 backing 校验，已剔除。"
    ]


def test_numeric_gate_keeps_dates_and_ranges_atomic() -> None:
    backing = "观察日为 2026-01-05 和 2026-12-31；另有 10 天与 14 天记录。"

    assert _unsupported_numbers("观察日改成 2026-01-31。", backing) == [
        "date:2026-01-31"
    ]
    assert _unsupported_numbers("等待期是 10-14 天。", backing) == [
        "range:10..14"
    ]


def test_composer_can_return_valid_card_when_no_llm_backing_exists() -> None:
    card = card_province_mapping_debt()
    provider = FakeLLMProvider(responses=[{"claims": []}])

    result = NarrativeComposer(provider, model="fake").compose(card)

    assert result.accepted_claims == []
    assert result.public_payload()["view"] == "data_debt"


def test_fake_provider_validates_response_schema() -> None:
    provider = FakeLLMProvider(responses=[{"claims": [{"text": "缺字段"}]}])

    with pytest.raises(ValidationError):
        provider.generate(
            response_model=NarrativeDraft,
            system_prompt="test",
            payload={},
            model="fake",
        )


class _ResponsesStub:
    def __init__(self, output_parsed: object, *, error: Exception | None = None) -> None:
        self.output_parsed = output_parsed
        self.error = error
        self.calls: list[dict] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            output_parsed=self.output_parsed,
            id="resp-test",
            model="gpt-test-snapshot",
            usage=SimpleNamespace(input_tokens=12, output_tokens=4),
        )


def test_openai_provider_uses_responses_parse_and_records_metadata() -> None:
    parsed = ParsedQuestion.model_validate(_parser_payload({
        "question": "为什么 ST？",
        "research_context": _context("603398"),
    }))
    responses = _ResponsesStub(parsed)
    provider = OpenAIResponsesProvider(client=SimpleNamespace(responses=responses))

    result = provider.generate(
        response_model=ParsedQuestion,
        system_prompt="system",
        payload={"question": "为什么 ST？", "research_context": _context("603398")},
        model="gpt-test",
    )

    assert result == parsed
    call = responses.calls[0]
    assert call["text_format"] is ParsedQuestion
    assert call["store"] is False
    assert "stream" not in call
    assert provider.last_generation.response_id == "resp-test"
    assert provider.last_generation.input_tokens == 12


def test_openai_provider_wraps_timeout_without_leaking_raw_output() -> None:
    responses = _ResponsesStub(None, error=TimeoutError("secret transport details"))
    provider = OpenAIResponsesProvider(client=SimpleNamespace(responses=responses))

    with pytest.raises(LLMProviderError, match="TimeoutError") as caught:
        provider.generate(
            response_model=NarrativeDraft,
            system_prompt="system",
            payload={},
            model="gpt-test",
        )
    assert "secret transport details" not in str(caught.value)


def test_openai_provider_rejects_unparsed_output() -> None:
    provider = OpenAIResponsesProvider(
        client=SimpleNamespace(responses=_ResponsesStub(None))
    )

    with pytest.raises(LLMProviderError, match="拒绝解析自由文本 JSON"):
        provider.generate(
            response_model=NarrativeDraft,
            system_prompt="system",
            payload={},
            model="gpt-test",
        )


def test_provider_loads_local_secrets_without_overriding_process_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_file = tmp_path / "v8_copilot.env"
    env_file.write_text(
        "OPENAI_API_KEY=from-file\nV8_OPENAI_MODEL=from-file-model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "LOCAL_SECRETS_FILE", env_file)
    monkeypatch.setenv("OPENAI_API_KEY", "already-set")

    import openai

    captured: dict[str, object] = {}

    def fake_openai(*, api_key=None, timeout=None):
        captured["api_key_arg"] = api_key
        captured["environment_key"] = os.environ["OPENAI_API_KEY"]
        captured["timeout"] = timeout
        return SimpleNamespace(responses=_ResponsesStub(NarrativeDraft(claims=[])))

    monkeypatch.setattr(openai, "OpenAI", fake_openai)
    provider = OpenAIResponsesProvider(timeout_seconds=9.0)
    provider.generate(
        response_model=NarrativeDraft,
        system_prompt="system",
        payload={},
        model="gpt-test",
    )

    assert captured == {
        "api_key_arg": None,
        "environment_key": "already-set",
        "timeout": 9.0,
    }


def test_missing_api_key_degrades_inside_safe_parser_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_file = tmp_path / "v8_copilot.env"
    env_file.write_text("V8_OPENAI_MODEL=gpt-test\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_SECRETS_FILE", env_file)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("V8_OPENAI_MODEL", raising=False)

    result = QuestionParser(OpenAIResponsesProvider()).parse_or_fallback(
        "为什么 ST？",
        _context("603398"),
        authoritative_object={"kind": "stock", "ref": "603398"},
    )

    assert result.llm_used is False
    assert result.adjudicated_route.predicted_route == "answer_query"
    assert result.degraded_reasons == ["LLM 问题解析降级: LLMProviderError"]
