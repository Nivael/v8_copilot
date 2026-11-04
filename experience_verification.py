"""Bind software verification to the method and code that were actually checked."""
from __future__ import annotations

import hashlib
from pathlib import Path

from canonical_json import digest
from experience_contract import ExperienceRecord
from settings import DATA_ROOT, PROJECT_ROOT

READONLY_AUDIT_PATH = DATA_ROOT / "local_data/v8_copilot/learning_audit/latest.json"


def method_digest(record: ExperienceRecord) -> str:
    return digest(record.model_dump(mode="json"))


def inventory_digest(records: list[ExperienceRecord]) -> str:
    return digest([record.model_dump(mode="json") for record in sorted(records, key=lambda row: row.experience_id)])


def software_digest(project_root: Path = PROJECT_ROOT) -> str:
    paths = set(project_root.glob("*.py"))
    for directory in ("llm", "evals", "tests", "contracts"):
        paths.update(path for path in (project_root / directory).rglob("*")
                     if path.is_file() and path.suffix in {".py", ".json", ".jsonl"})
    paths.update(project_root / name for name in ("pyproject.toml", "uv.lock", ".python-version")
                 if (project_root / name).is_file())
    result = hashlib.sha256()
    for path in sorted(paths):
        name = path.relative_to(project_root).as_posix().encode()
        payload = path.read_bytes()
        result.update(len(name).to_bytes(8, "big") + name)
        result.update(len(payload).to_bytes(8, "big") + payload)
    return result.hexdigest()
