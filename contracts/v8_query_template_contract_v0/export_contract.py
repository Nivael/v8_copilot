from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from query_templates import (  # noqa: E402
    QUERY_TEMPLATE_CONTRACT_VERSION,
    QueryTemplate,
    TEMPLATES,
)


HERE = Path(__file__).resolve().parent


def main() -> None:
    schema = TypeAdapter(QueryTemplate).json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = QUERY_TEMPLATE_CONTRACT_VERSION
    (HERE / "schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "registry.json").write_text(
        json.dumps(
            [template.model_dump(mode="json") for template in TEMPLATES],
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
