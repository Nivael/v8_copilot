from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from canonical_json import digest
from experience_audit import audit_inventory
from experience_contract import ExperienceCandidateInput, ExperienceReviewRequest, ExperienceStatus
from experience_governance import RegressionCheckResult
from learning_status import build_learning_status
from research_repository import ExperienceRepository


class Executor:
    def __init__(self, status="passed"):
        self.status = status
    def run(self, ref):
        return RegressionCheckResult(validation_ref=ref, status=self.status, detail="controlled software check")


def inventory(tmp_path):
    repository = ExperienceRepository(tmp_path / "experiences.sqlite3")
    value = ExperienceCandidateInput(
        experience_type="query_plan", title="比较先统一主体", value_summary="只比较同一主体口径。",
        trigger_conditions=["比较"], scope=["comparison"], required_inputs=["entity"],
        answer_rubric=["先说明主体"], anti_patterns=["混用母子公司"], coverage_boundaries=["不推断整体优劣"],
        validation_refs=["regression:entity_scope_boundary"], source_run_refs=["migration:test"],
    )
    row = repository.propose(value)
    accepted = repository.review(row.experience_id, ExperienceReviewRequest(action="accept", actor_type="human", reviewed_by="owner"))
    return repository, accepted, value


@pytest.mark.parametrize("status", ["passed", "failed", "unverified"])
def test_copy_audit_reports_result_without_changing_owner_decision(tmp_path, status):
    repo, row, _ = inventory(tmp_path)
    before = hashlib.sha256(repo.path.read_bytes()).hexdigest()
    path = tmp_path / "audit/latest.json"
    audit = audit_inventory(source=repo.path, output=path, executor=Executor(status))
    assert audit["status"] == "complete"
    assert audit["report"][status] == 1
    assert audit["source_unchanged"] is True
    assert repo.get(row.experience_id).status == ExperienceStatus.ACCEPTED
    assert hashlib.sha256(repo.path.read_bytes()).hexdigest() == before
    view = build_learning_status(experience_db=repo.path, ledger_db=tmp_path / "missing-ledger",
                                 governance_db=tmp_path / "missing-governance", freshness_path=tmp_path / "missing-freshness",
                                 audit_path=path)
    assert view["readonly_audit"]["availability"] == "current"
    assert view["regression_counts"]["current" if status == "passed" else status] == 1
    assert view["methods"][0]["verification_source"] == "readonly_audit"


def test_changed_method_invalidates_a_previously_passing_audit(tmp_path):
    repo, _, value = inventory(tmp_path)
    path = tmp_path / "audit/latest.json"
    audit_inventory(source=repo.path, output=path, executor=Executor())
    repo.propose(value.model_copy(update={"validation_refs": ["regression:entity_scope_boundary", "regression:new"]}))
    view = build_learning_status(experience_db=repo.path, audit_path=path, governance_db=tmp_path / "missing")
    assert view["readonly_audit"]["availability"] == "stale"
    assert view["regression_counts"] is None


def test_audit_with_impossible_pass_totals_is_rejected_even_with_matching_digest(tmp_path):
    repo, _, _ = inventory(tmp_path)
    path = tmp_path / "audit/latest.json"
    audit = audit_inventory(source=repo.path, output=path, executor=Executor())
    audit.pop("content_digest")
    audit["report"]["passed"] = 9
    audit["content_digest"] = digest(audit)
    path.write_text(json.dumps(audit))
    view = build_learning_status(experience_db=repo.path, audit_path=path, governance_db=tmp_path / "missing")
    assert view["readonly_audit"]["availability"] == "invalid"
    assert view["regression_counts"] is None


def test_expired_copy_audit_does_not_stay_current(tmp_path):
    repo, _, _ = inventory(tmp_path)
    path = tmp_path / "audit/latest.json"
    audit_inventory(source=repo.path, output=path, executor=Executor())
    view = build_learning_status(experience_db=repo.path, audit_path=path, governance_db=tmp_path / "missing",
                                 now=datetime.now(timezone.utc) + timedelta(days=31))
    assert view["readonly_audit"]["availability"] == "expired"
    assert view["regression_counts"] is None
