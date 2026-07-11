from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from question_cards import (  # noqa: E402
    QUESTION_CARD_CONTRACT_VERSION,
    QuestionCard,
)


HERE = Path(__file__).resolve().parent


def main() -> None:
    schema = TypeAdapter(QuestionCard).json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = QUESTION_CARD_CONTRACT_VERSION
    fixture = QuestionCard.model_validate({
        "id": "QC-20260710-011",
        "question": "同一重整招募问题按省份分层如何？",
        "object": {"kind": "cohort", "ref": "restructuring_investor_recruitment"},
        "needs_data": ["symbol_to_province"],
        "status": "needs_data",
        "view": "data_debt",
        "source": "system_gap",
        "debt_ref": "D-051A",
        "created_from": [{"kind": "data_debt", "ref": "D-051A"}],
    })
    (HERE / "schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "fixture.json").write_text(
        fixture.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
