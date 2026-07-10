import json
from pathlib import Path

import pytest

from lens_binding import LensRegistry


def library_payload(records: list[dict] | None = None) -> dict:
    return {
        "library_version": "test_library_v1",
        "frozen_at": "2026-07-10T00:00:00Z",
        "records": records if records is not None else [{
            "release_id": "RL-TEST-001",
            "release_role": "evidence_lens",
            "logic_chain_summary": "测试主题：测试逻辑链",
            "provenance_refs": ["fixture#001"],
            "sample_n": {"trigger": 2, "control": 3},
            "cohort_id": "test:cohort",
            "evidence_grade": "aggregate_weak",
            "validation_report_ref": "fixture/report.json",
            "v8_allowed_wording": "May describe the bounded test result.",
        }],
    }


def write_library(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_registry_loads_valid_file_and_invokes_record(tmp_path: Path) -> None:
    payload = library_payload()
    payload["records"][0]["logic_chain_summary"] = "逻辑链" * 80
    payload["records"][0]["provenance_refs"] = [f"fixture#{index}" for index in range(5)]
    path = write_library(tmp_path / "library.json", payload)
    registry = LensRegistry(path)

    record = registry.get("RL-TEST-001")
    invocation = registry.invoke(record, "测试答案段")

    assert registry.library_version == "test_library_v1"
    assert invocation.release_id == "RL-TEST-001"
    assert invocation.lens_kind == "evidence"
    assert invocation.to_dict()["forbidden_wording"] == []
    assert invocation.to_dict()["logic_chain_summary"] == payload["records"][0]["logic_chain_summary"]
    assert invocation.to_dict()["provenance_refs"] == payload["records"][0]["provenance_refs"]


def test_registry_fails_loudly_when_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="release library 不存在"):
        LensRegistry(tmp_path / "missing.json")


def test_registry_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "library.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON 非法"):
        LensRegistry(path)


def test_registry_rejects_duplicate_release_ids(tmp_path: Path) -> None:
    record = library_payload()["records"][0]
    path = write_library(tmp_path / "library.json", library_payload([record, dict(record)]))

    with pytest.raises(ValueError, match="release_id 重复"):
        LensRegistry(path)


def test_registry_rejects_incomplete_evidence_record(tmp_path: Path) -> None:
    record = library_payload()["records"][0]
    del record["sample_n"]
    path = write_library(tmp_path / "library.json", library_payload([record]))

    with pytest.raises(ValueError, match="evidence record.*缺字段"):
        LensRegistry(path)


def test_registry_rejects_unknown_release_role(tmp_path: Path) -> None:
    record = library_payload()["records"][0]
    record["release_role"] = "unknown_role"
    path = write_library(tmp_path / "library.json", library_payload([record]))

    with pytest.raises(ValueError, match="release_role 非法"):
        LensRegistry(path)
