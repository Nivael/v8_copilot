from __future__ import annotations

from pathlib import Path

from llm.providers import FakeLLMProvider
from p8_llm_extraction import BodyChunkExtraction, _cache_path, extract_announcement, locate_quote


def test_locate_quote_tolerates_pdf_whitespace() -> None:
    assert locate_quote("法院已裁定 受理\n公司重整。", "法院已裁定受理公司重整") == (0, 13)


def test_cache_key_isolated_by_announcement_and_contract(tmp_path: Path) -> None:
    first = _cache_path(
        tmp_path, announcement_id="ann-1", digest="a" * 64,
        model="fake/model", chunk_index=0,
    )
    second = _cache_path(
        tmp_path, announcement_id="ann-2", digest="a" * 64,
        model="fake/model", chunk_index=0,
    )
    assert first != second
    assert "p8_body_extraction_contract_v2" in first.parts
    assert "p8_body_extraction_v2" in first.parts


def test_rule_and_llm_agreement_is_body_verified(tmp_path: Path) -> None:
    body = "人民法院已经裁定受理公司重整，后续事项将另行公告。"

    def factory():
        return FakeLLMProvider(responses=[{
            "document_relevant": True,
            "nodes": [{
                "node": "formal_restructuring_accepted",
                "evidence_quote": "裁定受理公司重整",
                "confidence": "high",
                "issuer_scope": "listed_company",
            }],
            "key_facts": [],
            "no_event_reason": "",
        }])

    record = extract_announcement(
        {
            "announcement_id": "123", "symbol": "000001",
            "available_as_of": "2026-01-02", "title": "进展公告",
        },
        body,
        model="fake-model", cache_dir=tmp_path, provider_factory=factory,
    )
    assert record.reconciliation == "agreement"
    assert record.evidence_status == "body_verified"
    assert record.deterministic_nodes == ["formal_restructuring_accepted"]
    assert [item.node for item in record.llm_nodes] == ["formal_restructuring_accepted"]


def test_llm_only_node_stays_conflicted(tmp_path: Path) -> None:
    body = "公司说明，人民法院今日正式受理本公司的司法重整程序。"

    def factory():
        return FakeLLMProvider(responses=[BodyChunkExtraction.model_validate({
            "document_relevant": True,
            "nodes": [{
                "node": "formal_restructuring_accepted",
                "evidence_quote": "人民法院今日正式受理本公司的司法重整程序",
                "confidence": "high",
                "issuer_scope": "listed_company",
            }],
            "key_facts": [],
            "no_event_reason": "",
        })])

    record = extract_announcement(
        {
            "announcement_id": "456", "symbol": "000002",
            "available_as_of": "2026-01-03", "title": "进展公告",
        },
        body,
        model="fake-model", cache_dir=tmp_path, provider_factory=factory,
    )
    assert record.reconciliation == "conflict"
    assert record.evidence_status == "conflicted"
    assert "llm_only_node" in record.conflict_reasons


def test_invalid_quote_cannot_become_evidence(tmp_path: Path) -> None:
    def factory():
        return FakeLLMProvider(responses=[{
            "document_relevant": True,
            "nodes": [{
                "node": "plan_approved",
                "evidence_quote": "并不存在于正文中的句子",
                "confidence": "high",
                "issuer_scope": "listed_company",
            }],
            "key_facts": [],
            "no_event_reason": "",
        }])

    record = extract_announcement(
        {
            "announcement_id": "789", "symbol": "000003",
            "available_as_of": "2026-01-04", "title": "进展公告",
        },
        "本公告仅说明例行进展。",
        model="fake-model", cache_dir=tmp_path, provider_factory=factory,
    )
    assert record.invalid_proposal_count == 1
    assert record.llm_nodes == []
    assert record.evidence_status != "body_verified"


def test_old_shareholder_ledger_fact_types_keep_verbatim_spans(tmp_path: Path) -> None:
    body = "投资人受让1.5亿股，转增后总股本为6亿股，原股东保留2亿股。"

    def factory():
        return FakeLLMProvider(responses=[{
            "document_relevant": True,
            "nodes": [],
            "key_facts": [{
                "fact_type": "old_shareholder_retained_share_count",
                "value": "2", "unit": "亿股", "evidence_quote": "原股东保留2亿股",
            }],
            "no_event_reason": "",
        }])

    record = extract_announcement(
        {
            "announcement_id": "ledger-1", "symbol": "000004",
            "available_as_of": "2026-01-05", "title": "重整投资协议",
        },
        body, model="fake-model", cache_dir=tmp_path, provider_factory=factory,
    )
    assert record.key_facts[0].fact_type == "old_shareholder_retained_share_count"
    assert record.key_facts[0].evidence_quote == "原股东保留2亿股"
    assert record.key_facts[0].start_offset == body.index("原股东")
