"""Bind software verification to the method and code that were actually checked."""
from __future__ import annotations

import hashlib
from pathlib import Path

from canonical_json import digest
from experience_contract import ExperienceRecord
from settings import DATA_ROOT, PROJECT_ROOT

READONLY_AUDIT_PATH = DATA_ROOT / "local_data/v8_copilot/learning_audit/latest.json"
SOFTWARE_INPUT_SCOPE = 'software_rule_inputs_v2'
SOFTWARE_INPUT_SUFFIXES = {'.py', '.json', '.jsonl'}
SOFTWARE_INPUT_DIRECTORIES = ('llm', 'evals', 'tests', 'contracts', 'benchmarks', 'pilot_manifests')


def method_digest(record: ExperienceRecord) -> str:
    return digest(record.model_dump(mode="json"))


def inventory_digest(records: list[ExperienceRecord]) -> str:
    return digest([record.model_dump(mode="json") for record in sorted(records, key=lambda row: row.experience_id)])


def software_digest(project_root: Path = PROJECT_ROOT) -> str:
    # Root JSON profiles change parsing and study rules just as Python code does.
    # Deliberately stay within source/configuration trees, excluding runtime data.
    paths = {path for path in project_root.iterdir()
             if path.is_file() and path.suffix.lower() in SOFTWARE_INPUT_SUFFIXES}
    for directory in SOFTWARE_INPUT_DIRECTORIES:
        paths.update(path for path in (project_root / directory).rglob("*")
                     if path.is_file() and path.suffix.lower() in SOFTWARE_INPUT_SUFFIXES)
    paths.update(project_root / name for name in ("pyproject.toml", "uv.lock", ".python-version")
                 if (project_root / name).is_file())
    result = hashlib.sha256()
    result.update(SOFTWARE_INPUT_SCOPE.encode('utf-8') + b'\0')
    for path in sorted(paths):
        name = path.relative_to(project_root).as_posix().encode()
        payload = path.read_bytes()
        result.update(len(name).to_bytes(8, "big") + name)
        result.update(len(payload).to_bytes(8, "big") + payload)
    return result.hexdigest()
