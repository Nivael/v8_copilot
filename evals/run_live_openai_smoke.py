from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from answer_engine import card_calendar_regime_evidence
from llm.composer import NarrativeComposer
from llm.parser import QuestionParser
from llm.providers import OpenAIResponsesProvider


def _context(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "date_range": None,
        "selected_event": None,
        "selected_episode": None,
        "selected_lenses": [],
        "active_question": None,
        "answer_card_id": None,
    }


def main() -> int:
    provider = OpenAIResponsesProvider(timeout_seconds=30.0)
    parser_result = QuestionParser(provider).parse_or_fallback(
        "沐邦股份当前有哪些公开事件窗口值得核查？",
        _context("603398"),
        authoritative_object={"kind": "stock", "ref": "603398"},
    )
    parser_metadata = provider.last_generation

    card = card_calendar_regime_evidence("RL-A-001")
    composition = NarrativeComposer(provider).compose_or_fallback(card)
    composer_metadata = provider.last_generation

    live_validated = parser_result.llm_used and composition.llm_used
    if live_validated and not composition.accepted_claims:
        print("[FAIL] live composer produced no validated claim blocks")
        return 1
    if live_validated and composition.rejected_claims:
        print(f"[FAIL] live composer produced {len(composition.rejected_claims)} rejected claims")
        return 1

    print(json.dumps({
        "status": "ok" if live_validated else "degraded",
        "live_validated": live_validated,
        "route": parser_result.adjudicated_route.predicted_route,
        "llm_route_overruled": parser_result.llm_route_overruled,
        "validated_claim_count": len(composition.accepted_claims),
        "degraded_reasons": [
            *parser_result.degraded_reasons,
            *(composition.degraded_reasons or []),
        ],
        "parser_generation": asdict(parser_metadata) if parser_metadata else None,
        "composer_generation": asdict(composer_metadata) if composer_metadata else None,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
