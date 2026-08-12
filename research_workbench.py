"""Local CLI used by the Codex ST research skill.

Evidence commands are read-only. Recording, feedback and candidate proposal write only
to the dedicated local run/experience repositories.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from api_contract import ResearchObject, ResearchRequest
from evidence_gateway import (
    EvidencePack,
    ExternalEvidenceInput,
    ResearchDraft,
    ValidationReport,
    augment_evidence_pack,
    build_evidence_pack,
    plan_evidence_acquisition,
    validate_research_draft,
)
from experience_contract import ExperienceCandidateInput, ExperienceFeedbackRequest, ExperienceStatus
from experience_auto_accept import auto_accept_candidate
from experience_distiller import distill_run_feedback
from research_repository import ExperienceRepository, ResearchRunCreate, ResearchRunLedger
from settings import (
    ACCEPTED_EXPERIENCE_REGISTRY_PATH,
    EXPERIENCE_REPOSITORY_DB,
    RESEARCH_RUN_LEDGER_DB,
)


def _write_or_print(payload: dict | list, output: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output)}, ensure_ascii=False))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry_output(repository: ExperienceRepository) -> Path:
    if repository.path == EXPERIENCE_REPOSITORY_DB:
        return ACCEPTED_EXPERIENCE_REGISTRY_PATH
    return repository.path.parent / "accepted_experiences_v1.json"


def _digest(value: dict) -> str:
    import hashlib

    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _render_answer(draft: ResearchDraft) -> str:
    narrative = draft.narrative
    parts = [narrative.direct_answer.text]
    if narrative.reasoning_steps:
        parts.append("判断依据\n" + "\n".join(
            f"{index}. {step.title}：{step.text}"
            for index, step in enumerate(narrative.reasoning_steps, 1)
        ))
    if narrative.uncertainties:
        parts.append("不确定性\n" + "\n".join(
            f"- {item.text}" for item in narrative.uncertainties
        ))
    if narrative.watch_items:
        parts.append("后续观察\n" + "\n".join(
            f"- {item.text}" for item in narrative.watch_items
        ))
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="ST Research Codex workbench")
    sub = parser.add_subparsers(dest="command", required=True)

    evidence = sub.add_parser("evidence")
    evidence.add_argument("--question", required=True)
    evidence.add_argument("--object-kind")
    evidence.add_argument("--object-ref")
    evidence.add_argument("--request-id")
    evidence.add_argument("--output", type=Path)

    validate = sub.add_parser("validate")
    validate.add_argument("--pack", type=Path, required=True)
    validate.add_argument("--draft", type=Path, required=True)
    validate.add_argument("--output", type=Path)

    network_plan = sub.add_parser("network-plan")
    network_plan.add_argument("--pack", type=Path, required=True)
    network_plan.add_argument("--output", type=Path)

    augment = sub.add_parser("augment")
    augment.add_argument("--pack", type=Path, required=True)
    augment.add_argument("--external-evidence", type=Path, required=True)
    augment.add_argument("--output", type=Path, required=True)

    record = sub.add_parser("record")
    record.add_argument("--pack", type=Path, required=True)
    record.add_argument("--draft", type=Path, required=True)
    record.add_argument("--validation", type=Path, required=True)
    record.add_argument("--surface", default="codex_desktop")
    record.add_argument("--model", default="")
    record.add_argument("--thread-id", default="")
    record.add_argument("--turn-id", default="")

    feedback = sub.add_parser("feedback")
    feedback.add_argument("--run-id", required=True)
    feedback.add_argument("--category", required=True, choices=[
        "presentation", "routing", "coverage", "query_plan", "anti_pattern",
        "no_experience",
    ])
    feedback.add_argument("--text", required=True)
    feedback.add_argument("--submitted-by", default="owner")

    experiences = sub.add_parser("experiences")
    experiences.add_argument("--status", choices=[item.value for item in ExperienceStatus])
    experiences.add_argument("--limit", type=int, default=100)

    propose = sub.add_parser("propose")
    propose.add_argument("--candidate", type=Path, required=True)

    args = parser.parse_args()
    experience_repo = ExperienceRepository(EXPERIENCE_REPOSITORY_DB)
    ledger = ResearchRunLedger(RESEARCH_RUN_LEDGER_DB)

    if args.command == "evidence":
        if bool(args.object_kind) != bool(args.object_ref):
            parser.error("--object-kind and --object-ref must be provided together")
        research_object = (
            ResearchObject(kind=args.object_kind, ref=args.object_ref)
            if args.object_kind else None
        )
        pack = build_evidence_pack(
            ResearchRequest(
                question=args.question,
                request_id=args.request_id,
                object=research_object,
                llm_mode="off",
            ),
            experience_repository=experience_repo,
        )
        _write_or_print(pack.model_dump(mode="json"), args.output)
        return 0

    if args.command == "validate":
        pack = EvidencePack.model_validate(_read_json(args.pack))
        draft = ResearchDraft.model_validate(_read_json(args.draft))
        report = validate_research_draft(pack, draft)
        _write_or_print(report.model_dump(mode="json"), args.output)
        return 0 if report.valid else 2

    if args.command == "network-plan":
        pack = EvidencePack.model_validate(_read_json(args.pack))
        plan = plan_evidence_acquisition(pack)
        _write_or_print(plan.model_dump(mode="json"), args.output)
        return 0

    if args.command == "augment":
        pack = EvidencePack.model_validate(_read_json(args.pack))
        raw = json.loads(args.external_evidence.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else raw.get("items")
        if not isinstance(rows, list):
            raise SystemExit("external evidence 必须是 list 或包含 items list")
        inputs = [ExternalEvidenceInput.model_validate(row) for row in rows]
        augmented = augment_evidence_pack(pack, inputs)
        _write_or_print(augmented.model_dump(mode="json"), args.output)
        return 0

    if args.command == "record":
        pack = EvidencePack.model_validate(_read_json(args.pack))
        draft = ResearchDraft.model_validate(_read_json(args.draft))
        report = ValidationReport.model_validate(_read_json(args.validation))
        if (
            not report.valid
            or report.pack_id != pack.pack_id
            or report.pack_digest != pack.pack_digest
            or report.draft_digest != _digest(draft.model_dump(mode="json"))
        ):
            raise SystemExit("refusing to record an invalid or mismatched answer")
        if draft.decision_audit is None:
            raise SystemExit("refusing to record without a structured decision_audit")
        ledger.store_evidence_pack(pack.model_dump(mode="json"))
        scope = pack.question_scope
        record_value = ledger.record(ResearchRunCreate(
            request_id=str(pack.deterministic_response.get("request_id") or pack.pack_id),
            question_text=str(scope["question"]),
            normalized_intent=str(scope["intent"]),
            object_refs=[str(scope["object"].get("ref") or "unknown")],
            evidence_pack_ids=[pack.pack_id],
            final_answer=_render_answer(draft),
            research_draft=draft.model_dump(mode="json"),
            decision_audit=draft.decision_audit.model_dump(mode="json"),
            validation_report=report.model_dump(mode="json"),
            source_freshness=pack.source_freshness,
            tool_calls=[pack.query_plan_id, "validate_research_draft"],
            experience_hits=[row.experience_id for row in pack.applicable_experiences],
            agent_surface=args.surface,
            model=args.model,
            thread_id=args.thread_id,
            turn_id=args.turn_id,
        ))
        _write_or_print(record_value.model_dump(mode="json"), None)
        return 0

    if args.command == "feedback":
        request = ExperienceFeedbackRequest(
            category=args.category,
            feedback_text=args.text,
            submitted_by=args.submitted_by,
        )
        feedback_id = ledger.add_feedback(
            args.run_id,
            category=request.category,
            feedback_text=request.feedback_text,
            submitted_by=request.submitted_by,
        )
        candidate_input = distill_run_feedback(ledger.get(args.run_id), request)
        candidate = experience_repo.propose(candidate_input) if candidate_input else None
        auto_acceptance = None
        if candidate:
            ledger.link_experience(args.run_id, candidate.experience_id, "candidate_source")
            auto_acceptance = auto_accept_candidate(
                candidate, repository=experience_repo, ledger=ledger,
                registry_output=_registry_output(experience_repo),
            )
            candidate = experience_repo.get(candidate.experience_id)
        _write_or_print({
            "feedback_id": feedback_id,
            "experience_candidate": (
                candidate.model_dump(mode="json") if candidate else None
            ),
            "auto_acceptance": (
                auto_acceptance.model_dump(mode="json") if auto_acceptance else None
            ),
        }, None)
        return 0

    if args.command == "experiences":
        selected = ExperienceStatus(args.status) if args.status else None
        rows = experience_repo.list(status=selected, limit=args.limit)
        _write_or_print([row.model_dump(mode="json") for row in rows], None)
        return 0

    candidate = ExperienceCandidateInput.model_validate(_read_json(args.candidate))
    result = experience_repo.propose(candidate)
    auto_accept_candidate(
        result, repository=experience_repo, ledger=ledger,
        registry_output=_registry_output(experience_repo),
    )
    result = experience_repo.get(result.experience_id)
    _write_or_print(result.model_dump(mode="json"), None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
