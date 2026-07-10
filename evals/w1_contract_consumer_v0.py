from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


CONTRACT_VERSION = "v8_copilot_api_contract_v0"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT_ROOT = REPO_ROOT / "contracts" / CONTRACT_VERSION


def contract_root() -> Path:
    configured = os.getenv("V8_API_CONTRACT_ROOT")
    return Path(configured) if configured else DEFAULT_CONTRACT_ROOT


def load_schema() -> dict[str, Any]:
    path = contract_root() / "schema.json"
    if not path.exists():
        raise FileNotFoundError(
            f"W1 API contract 未合入或未配置 V8_API_CONTRACT_ROOT: {path}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("x-contract-version") != CONTRACT_VERSION:
        raise ValueError(f"W1 contract version 不匹配: {data.get('x-contract-version')}")
    return data


def load_fixture(name: str) -> dict[str, Any]:
    path = contract_root() / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_definition(name: str, payload: dict[str, Any]) -> None:
    schema = load_schema()
    if name not in schema.get("$defs", {}):
        raise KeyError(f"W1 contract 无定义: {name}")
    wrapper = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{name}",
    }
    Draft202012Validator(wrapper).validate(payload)
