from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api_contract_v2 import (  # noqa: E402
    API_CONTRACT_VERSION_V2,
    public_contract_schema_v2,
)


HERE = Path(__file__).resolve().parent


def main() -> None:
    schema = public_contract_schema_v2()
    (HERE / "schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "manifest.json").write_text(
        json.dumps({
            "contract_version": API_CONTRACT_VERSION_V2,
            "request_contract": "v8_copilot_api_contract_v0",
            "answer_contract": "v8_answer_contract_v0",
            "compatibility": "additive_response",
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
