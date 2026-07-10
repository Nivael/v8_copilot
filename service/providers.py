from __future__ import annotations

from typing import Protocol

from contracts.v8_copilot_api_contract_v0.models import (
    QuestionInterpretation,
    ResearchRequest,
    ValidatedClaim,
)


class InterpretationProvider(Protocol):
    """Optional LLM parser; deterministic routing still owns the final decision."""

    available: bool

    def interpret(
        self,
        *,
        request: ResearchRequest,
        deterministic: QuestionInterpretation,
    ) -> QuestionInterpretation: ...


class ClaimProvider(Protocol):
    """Injection boundary for W2 narrative providers.

    Providers receive only the validated AnswerCard and an allowlisted backing
    catalog. They never receive a database connection or filesystem path.
    """

    available: bool

    def compose(
        self,
        *,
        request: ResearchRequest,
        answer_card: dict,
        backing_catalog: dict[str, set[str]],
    ) -> list[ValidatedClaim]: ...


class InvalidClaimOutput(ValueError):
    pass


def backing_catalog(answer_card: dict) -> dict[str, set[str]]:
    return {
        "lens_invocation": {
            row["release_id"] for row in answer_card.get("lens_invocations", [])
        },
        "query_row": {row["row_id"] for row in answer_card.get("body_rows", [])},
        "provenance_ref": set(answer_card.get("provenance", [])),
        "data_debt": set(answer_card.get("data_debt_refs", [])),
        "lens_gap": {row["gap_id"] for row in answer_card.get("lens_gap", [])},
    }


def validate_claims(answer_card: dict, claims: list[ValidatedClaim]) -> None:
    catalog = backing_catalog(answer_card)
    claim_ids: set[str] = set()
    for claim in claims:
        if claim.claim_id in claim_ids:
            raise InvalidClaimOutput(f"duplicate claim_id: {claim.claim_id}")
        claim_ids.add(claim.claim_id)
        allowed = catalog.get(claim.backing.kind, set())
        if claim.backing.ref not in allowed:
            raise InvalidClaimOutput(
                f"unresolved backing: {claim.backing.kind}:{claim.backing.ref}"
            )
