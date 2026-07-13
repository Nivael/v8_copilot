"""API v1 enrichment: typed sedimentation, templates, and navigation."""
from __future__ import annotations

import re
from hashlib import sha256
from urllib.parse import urlencode

from api_contract import ResearchRequest, ResearchResponse
from api_contract_v1 import (
    NavigationRef,
    ResearchContextPatch,
    ResearchResponseV1,
    ResearchStreamEventV1,
)
from dossier_service import DossierNotFoundError, build_stock_dossier
from query_templates import template_for_rules
from question_cards import (
    DataDebtCandidate,
    QuestionCard,
    QuestionObject,
    QuestionOrigin,
    candidate_id,
)


QUESTION_DEBT = {
    "QC-20260710-006": ("D-021", "shareholder_count_full_coverage"),
    "QC-20260710-011": ("D-051A", "symbol_to_province_mapping"),
    "QC-20260710-012": ("D-051B", "out_of_court_or_in_court_flag"),
    "QC-20260710-013": ("C14", "as_of_market_cap"),
    "QC-20260710-014": ("D-051C", "market_index_daily_series"),
}


def _question_object(response: ResearchResponse) -> QuestionObject:
    obj = response.interpretation.object
    return QuestionObject(kind=obj.kind, ref=obj.ref)


def _question_view(response: ResearchResponse) -> str:
    view = response.route.view
    if view in {"evidence", "query", "checklist", "methodology", "data_debt"}:
        return view
    return "query"


def _question_cards(
    request: ResearchRequest,
    response: ResearchResponse,
) -> list[QuestionCard]:
    obj = _question_object(response)
    origins = [QuestionOrigin(kind="user_question", ref=response.request_id)]
    if response.route.route == "refuse_or_rewrite":
        subject = obj.ref if obj.kind == "stock" else "该研究对象"
        rewritten = f"{subject} 接下来该看哪些窗口？"
        return [QuestionCard(
            id=candidate_id(rewritten, obj.kind, obj.ref),
            question=rewritten,
            object=obj,
            status="answerable",
            view="checklist",
            source="user",
            created_from=origins,
        )]
    refs = list(response.route.question_card_refs)
    if not refs and response.route.route in {
        "lens_gap", "clarify", "needs_review", "refuse_or_rewrite"
    }:
        refs = [candidate_id(request.question, obj.kind, obj.ref)]

    active_debts = set(response.route.data_debt_refs)
    if response.answer_card:
        active_debts.update(response.answer_card.get("data_debt_refs", []))
    cards: list[QuestionCard] = []
    for raw_ref in refs:
        card_id = (
            candidate_id(request.question, obj.kind, obj.ref)
            if raw_ref == "question_card:new"
            else raw_ref
        )
        debt = QUESTION_DEBT.get(card_id)
        if debt and debt[0] not in active_debts:
            debt = None
        if debt:
            status = "needs_data"
            debt_ref, missing = debt
            needs_data = [missing]
            view = "data_debt"
        elif response.route.status == "answerable":
            status = "answerable"
            debt_ref = None
            needs_data = []
            view = _question_view(response)
        else:
            status = "needs_review"
            debt_ref = None
            needs_data = []
            view = _question_view(response)
        cards.append(QuestionCard(
            id=card_id,
            question=request.question,
            object=obj,
            needs_data=needs_data,
            status=status,
            view=view,
            source="system_gap" if response.gaps else "user",
            debt_ref=debt_ref,
            created_from=origins,
        ))

    return cards[:20]


def _data_debt_candidates(response: ResearchResponse) -> list[DataDebtCandidate]:
    rows = response.answer_card.get("data_debt", []) if response.answer_card else []
    by_ref = {
        str(row["debt_ref"]): (str(row["gap"]), str(row["affects"]))
        for row in rows
        if row.get("debt_ref")
    }
    candidates: list[DataDebtCandidate] = []
    for debt_ref in response.route.data_debt_refs:
        gap, affects = by_ref.get(
            debt_ref,
            ("当前研究所需字段不可用", "相关分层或比较无法可靠生成"),
        )
        candidates.append(DataDebtCandidate(
            debt_ref=debt_ref,
            gap=gap,
            affects=affects,
            created_from=[QuestionOrigin(kind="data_debt", ref=debt_ref)],
        ))
    for debt_ref, (gap, affects) in by_ref.items():
        if debt_ref not in response.route.data_debt_refs:
            candidates.append(DataDebtCandidate(
                debt_ref=debt_ref,
                gap=gap,
                affects=affects,
                created_from=[QuestionOrigin(kind="data_debt", ref=debt_ref)],
            ))
    return candidates[:20]


def _nav_id(kind: str, source_ref: str) -> str:
    digest = sha256(f"{kind}\x1f{source_ref}".encode()).hexdigest()[:12]
    return f"nav-{kind}-{digest}"


def _href(path: str, **params: str | None) -> str:
    query = urlencode({key: value for key, value in params.items() if value})
    return f"{path}?{query}" if query else path


def _research_href(
    request: ResearchRequest,
    response: ResearchResponse,
    *,
    symbol: str | None,
    added_lens: str | None = None,
    **focus: str,
) -> str:
    params: dict[str, str | list[str]] = {
        "question": request.question,
        "object_kind": response.interpretation.object.kind,
        "object_ref": response.interpretation.object.ref,
        **focus,
    }
    context = request.context
    if symbol:
        params["symbol"] = symbol
    if context:
        if context.selected_event:
            params["event"] = context.selected_event.event_id
            if context.selected_event.date:
                params["date"] = context.selected_event.date.isoformat()
            if context.selected_event.title:
                params["title"] = context.selected_event.title
        if context.selected_episode:
            params["episode"] = context.selected_episode
        if context.date_range:
            if context.date_range.start:
                params["start"] = context.date_range.start.isoformat()
            if context.date_range.end:
                params["end"] = context.date_range.end.isoformat()
        if context.answer_card_id:
            params["answer"] = context.answer_card_id
        lenses = list(context.selected_lenses)
    else:
        lenses = []
    if added_lens and added_lens not in lenses:
        lenses.append(added_lens)
    if lenses:
        params["lens"] = lenses
    return f"/?{urlencode(params, doseq=True)}"


def _add_navigation(
    refs: list[NavigationRef],
    *,
    kind: str,
    label: str,
    source_kind: str,
    source_ref: str,
    href: str,
    context: ResearchContextPatch,
) -> None:
    item = NavigationRef(
        id=_nav_id(kind, source_ref),
        kind=kind,
        label=label,
        source_kind=source_kind,
        source_ref=source_ref,
        href=href,
        context=context,
    )
    if item.id not in {existing.id for existing in refs}:
        refs.append(item)


def _navigation_refs(
    request: ResearchRequest,
    response: ResearchResponse,
) -> list[NavigationRef]:
    refs: list[NavigationRef] = []
    obj = response.interpretation.object
    symbol = obj.ref if obj.kind == "stock" and re.fullmatch(r"[0-9]{6}", obj.ref) else None
    if not symbol and request.context:
        symbol = request.context.symbol
    if not symbol and response.answer_card:
        match = re.search(r"stock:([0-9]{6})", response.answer_card["object_ref"])
        symbol = match.group(1) if match else None
    if symbol:
        _add_navigation(
            refs,
            kind="stock",
            label=symbol,
            source_kind="answer_card",
            source_ref=f"stock:{symbol}",
            href=f"/stocks/{symbol}",
            context=ResearchContextPatch(symbol=symbol),
        )

    card = response.answer_card or {}
    selected_row = next(
        (
            row for row in card.get("body_rows", [])
            if row.get("row_id") == "selected_event"
        ),
        None,
    )
    selected_event = request.context.selected_event if request.context else None
    if selected_event and symbol:
        selected_event_id = str(
            (selected_row or {}).get("事件编号") or selected_event.event_id
        )
        selected_event_title = str(
            (selected_row or {}).get("标题") or selected_event.title or selected_event_id
        )
        selected_event_date = (selected_row or {}).get("日期")
        event_date = selected_event_date or selected_event.date
        event_href = _href(
            f"/stocks/{symbol}",
            event=selected_event_id,
            date=str(event_date)[:10],
            title=selected_event_title,
        )
        _add_navigation(
            refs,
            kind="announcement",
            label=selected_event_title,
            source_kind="request_context",
            source_ref=selected_event_id,
            href=event_href,
            context=ResearchContextPatch(
                symbol=symbol,
                event_id=selected_event_id,
                event_title=selected_event_title,
                date_start=event_date,
                date_end=event_date,
            ),
        )
        if event_date:
            _add_navigation(
                refs,
                kind="date",
                label=str(event_date)[:10],
                source_kind="request_context",
                source_ref=str(event_date)[:10],
                href=event_href,
                context=ResearchContextPatch(
                    symbol=symbol, date_start=event_date, date_end=event_date
                ),
            )
        try:
            event = next(
                item for item in build_stock_dossier(symbol).events
                if item.event_id == selected_event_id
            )
        except (DossierNotFoundError, StopIteration):
            event = None
        if event:
            _add_navigation(
                refs,
                kind="episode",
                label=event.episode_label,
                source_kind="request_context",
                source_ref=event.episode_type,
                href=event_href,
                context=ResearchContextPatch(
                    symbol=symbol,
                    event_id=event.event_id,
                    episode_ref=event.episode_type,
                ),
            )

    for row in card.get("body_rows", []):
        announcement_id = row.get("巨潮公告ID") or row.get("公告编号")
        announcement_date = row.get("日期")
        if not announcement_id or not announcement_date or not symbol:
            continue
        announcement_ref = str(announcement_id)
        if not announcement_ref.startswith("announcement:"):
            announcement_ref = f"announcement:{announcement_ref}"
        event_href = _href(
            f"/stocks/{symbol}",
            event=announcement_ref,
            date=str(announcement_date)[:10],
            title=str(row.get("标题") or announcement_ref),
        )
        _add_navigation(
            refs,
            kind="announcement",
            label=str(row.get("标题") or announcement_ref),
            source_kind="answer_row",
            source_ref=announcement_ref,
            href=event_href,
            context=ResearchContextPatch(
                symbol=symbol,
                event_id=announcement_ref,
                event_title=str(row.get("标题") or "") or None,
                date_start=str(announcement_date)[:10],
                date_end=str(announcement_date)[:10],
            ),
        )
        _add_navigation(
            refs,
            kind="date",
            label=str(announcement_date)[:10],
            source_kind="answer_row",
            source_ref=f"{announcement_ref}:{str(announcement_date)[:10]}",
            href=event_href,
            context=ResearchContextPatch(
                symbol=symbol,
                event_id=announcement_ref,
                date_start=str(announcement_date)[:10],
                date_end=str(announcement_date)[:10],
            ),
        )
    for invocation in card.get("lens_invocations", []):
        release_id = str(invocation["release_id"])
        _add_navigation(
            refs,
            kind="lens",
            label=release_id,
            source_kind="lens_invocation",
            source_ref=release_id,
            href=_research_href(
                request, response, symbol=symbol, added_lens=release_id
            ),
            context=ResearchContextPatch(symbol=symbol, lens_id=release_id),
        )
    for provenance in card.get("provenance", []):
        provenance = str(provenance)
        _add_navigation(
            refs,
            kind="provenance",
            label=provenance,
            source_kind="provenance",
            source_ref=provenance,
            href=_research_href(
                request, response, symbol=symbol, provenance=provenance
            ),
            context=ResearchContextPatch(
                symbol=symbol, provenance_ref=provenance
            ),
        )
    for debt_ref in card.get("data_debt_refs", []):
        debt_ref = str(debt_ref)
        _add_navigation(
            refs,
            kind="data_debt",
            label=debt_ref,
            source_kind="data_debt",
            source_ref=debt_ref,
            href=_research_href(
                request, response, symbol=symbol, debt=debt_ref
            ),
            context=ResearchContextPatch(
                symbol=symbol, data_debt_ref=debt_ref
            ),
        )
    return refs[:200]


def enrich_response_v1(
    request: ResearchRequest,
    response: ResearchResponse,
) -> ResearchResponseV1:
    template = template_for_rules(response.route.matched_rules)
    return ResearchResponseV1(
        request_id=response.request_id,
        interpretation=response.interpretation,
        route=response.route,
        answer_card=response.answer_card,
        claims=response.claims,
        gaps=response.gaps,
        sedimentation_candidates=response.sedimentation_candidates,
        question_cards=_question_cards(request, response),
        data_debt_candidates=_data_debt_candidates(response),
        navigation_refs=_navigation_refs(request, response),
        query_template_id=template.template_id if template else None,
        degraded=response.degraded,
        degraded_reasons=response.degraded_reasons,
        llm_used=response.llm_used,
    )


def stream_events_v1(
    request: ResearchRequest,
    response: ResearchResponseV1,
) -> list[ResearchStreamEventV1]:
    events: list[ResearchStreamEventV1] = []

    def append(event: str, payload: dict) -> None:
        events.append(ResearchStreamEventV1(
            request_id=response.request_id,
            sequence=len(events) + 1,
            event=event,  # type: ignore[arg-type]
            payload=payload,
        ))

    append("accepted", {"llm_mode": request.llm_mode})
    append("interpreted", response.interpretation.model_dump(mode="json"))
    append("routed", {
        **response.route.model_dump(mode="json"),
        "query_template_id": response.query_template_id,
    })
    if response.answer_card is not None:
        append("answer_card", response.answer_card)
    if response.claims:
        append("claim_block", {
            "claims": [claim.model_dump(mode="json") for claim in response.claims]
        })
    if response.degraded:
        append("degraded", {"reasons": response.degraded_reasons})
    append("completed", {
        "route": response.route.route,
        "has_answer_card": response.answer_card is not None,
        "claim_count": len(response.claims),
        "response": response.model_dump(mode="json"),
    })
    return events
