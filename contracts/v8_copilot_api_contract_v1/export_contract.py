from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api_contract import (  # noqa: E402
    QuestionInterpretation,
    ResearchObject,
    RouteDecision,
)
from api_contract_v1 import (  # noqa: E402
    API_CONTRACT_VERSION_V1,
    NavigationRef,
    ResearchContextPatch,
    ResearchResponseV1,
    ResearchStreamEventV1,
    public_contract_schema_v1,
)
from question_cards import QuestionCard  # noqa: E402


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def dump(path: Path, payload: object) -> None:
    value = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    question_card = QuestionCard.model_validate({
        "id": "QC-CAND-0123456789ab",
        "question": "这个问题当前需要补充哪类数据？",
        "object": {"kind": "unknown", "ref": "unknown"},
        "needs_data": [],
        "status": "needs_review",
        "view": "query",
        "source": "system_gap",
        "created_from": [{"kind": "user_question", "ref": "req-fixture-v1"}],
    })
    interpretation = QuestionInterpretation(
        object=ResearchObject(kind="unknown", ref="unknown"),
        intent="research_question",
        ambiguities=["当前方法未覆盖"],
    )
    route = RouteDecision(
        route="lens_gap",
        status="needs_review",
        view="lens_gap",
        reason="稳定沉淀为问题卡。",
        matched_rules=["deterministic_unknown_fallback"],
        question_card_refs=[question_card.id],
        required_lens_behavior="lens_gap_required",
    )
    navigation = NavigationRef(
        id="nav-lens-rl-a-003",
        kind="lens",
        label="RL-A-003",
        source_kind="lens_invocation",
        source_ref="RL-A-003",
        href="/?lens=RL-A-003",
        context=ResearchContextPatch(lens_id="RL-A-003"),
    )
    response = ResearchResponseV1(
        request_id="req-fixture-v1",
        interpretation=interpretation,
        route=route,
        question_cards=[question_card],
        navigation_refs=[navigation],
        query_template_id=None,
    )
    event = ResearchStreamEventV1(
        request_id=response.request_id,
        sequence=1,
        event="completed",
        emitted_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
        payload={"response": response.model_dump(mode="json")},
    )
    dump(HERE / "schema.json", public_contract_schema_v1())
    dump(FIXTURES / "research_response.json", response)
    dump(FIXTURES / "navigation_ref.json", navigation)
    dump(FIXTURES / "question_card.json", question_card)
    (FIXTURES / "stream.ndjson").write_text(
        event.model_dump_json() + "\n", encoding="utf-8"
    )
    dump(HERE / "manifest.json", {
        "contract_version": API_CONTRACT_VERSION_V1,
        "schema": "schema.json",
        "fixtures": [
            "navigation_ref.json", "question_card.json", "research_response.json",
            "stream.ndjson",
        ],
    })


if __name__ == "__main__":
    main()
