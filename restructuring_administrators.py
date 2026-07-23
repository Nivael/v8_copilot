"""Append-only P6A restructuring-administrator facts.

The automatic materializer is deliberately conservative: it only accepts
listed-company announcements whose title and body both state that a court
selected or appointed an administrator.  Ambiguous rows are retained as
rejections instead of being guessed into the fact tables.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


CONTRACT_VERSION = "v8_restructuring_administrators_v1"
RELATED_ENTITY_TERMS = ("子公司", "孙公司", "控股股东", "参股公司")


class AdministratorEntityType(StrEnum):
    LAW_FIRM = "law_firm"
    ACCOUNTING_FIRM = "accounting_firm"
    LIQUIDATION_FIRM = "liquidation_firm"
    LIQUIDATION_GROUP = "liquidation_group"
    OTHER = "other"


class AppointmentKind(StrEnum):
    TEMPORARY_ADMINISTRATOR = "temporary_administrator"
    ADMINISTRATOR = "administrator"


class ParticipationRole(StrEnum):
    SOLE = "sole"
    JOINT = "joint"


class RestructuringEventType(StrEnum):
    ADMINISTRATOR_APPOINTED = "administrator_appointed"
    PRE_RESTRUCTURING_STARTED = "pre_restructuring_started"
    FORMAL_RESTRUCTURING_ACCEPTED = "formal_restructuring_accepted"
    INVESTOR_RECRUITMENT_STARTED = "investor_recruitment_started"
    RESTRUCTURING_PLAN_PUBLISHED = "restructuring_plan_published"
    RESTRUCTURING_PLAN_APPROVED = "restructuring_plan_approved"
    RESTRUCTURING_COMPLETED = "restructuring_completed"
    RESTRUCTURING_TERMINATED = "restructuring_terminated"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class AnnouncementSourceRow(_FrozenModel):
    announcement_id: str
    symbol: str = Field(pattern=r"^\d{6}$")
    announcement_date: date
    published_at: str = ""
    title: str
    url: str = ""
    body_text: str
    source: str


class SourceDocument(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    document_id: str
    announcement_id: str
    symbol: str
    title: str
    source_kind: Literal["official_issuer_announcement"] = "official_issuer_announcement"
    source_name: str
    source_url: str
    published_date: date
    published_at: str = ""
    body_sha256: str
    evidence_quote: str


class RestructuringCase(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    case_id: str
    symbol: str
    subject_kind: Literal["listed_company"] = "listed_company"
    official_case_number: str
    identity_basis: str


class AdministratorOrganization(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    organization_id: str
    canonical_name: str
    entity_type: AdministratorEntityType


class AdministratorAlias(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    alias_id: str
    organization_id: str
    alias: str
    source_document_id: str


class AdministratorAssignment(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    assignment_id: str
    case_id: str
    organization_id: str
    appointment_kind: AppointmentKind
    participation_role: ParticipationRole
    effective_date: date
    effective_date_basis: Literal["decision_date_in_quote", "announcement_date"]
    source_document_id: str


class RestructuringEvent(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    event_id: str
    case_id: str
    assignment_id: str
    event_type: RestructuringEventType
    event_date: date
    information_available_date: date
    source_document_id: str


class ExtractionRejection(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    rejection_id: str
    announcement_id: str
    symbol: str
    title: str
    reason: str


class ExtractionResult(_FrozenModel):
    accepted: bool
    source_document: SourceDocument | None = None
    case: RestructuringCase | None = None
    organizations: list[AdministratorOrganization] = Field(default_factory=list)
    aliases: list[AdministratorAlias] = Field(default_factory=list)
    assignments: list[AdministratorAssignment] = Field(default_factory=list)
    events: list[RestructuringEvent] = Field(default_factory=list)
    rejection: ExtractionRejection | None = None


class MaterializationSummary(_FrozenModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    run_id: str
    source_database: str
    database: str
    start_date: date | None
    through: date | None
    candidates_scanned: int
    documents_accepted: int
    documents_rejected: int
    organizations_seen: int
    assignments_seen: int
    events_seen: int
    generated_at: datetime


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def _payload(model: BaseModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("【", "[").replace("】", "]")


def _canonical_case_number(text: str) -> str:
    compact = _compact(text).replace("(", "（").replace(")", "）")
    match = re.search(r"（\d{4}）[^，。；;]{0,18}?破申\d+号(?:之一)?", compact)
    return match.group(0).removesuffix("之一") if match else ""


def _issuer_name(text: str) -> str:
    compact = _compact(text[:1200])
    matches = re.findall(
        r"([\u4e00-\u9fff]{2,35}(?:集团)?股份有限公司)(?=关于|（以下简称|\()",
        compact,
    )
    return min(matches, key=len) if matches else ""


def _parse_date(raw: str) -> date | None:
    match = re.search(r"(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})日?", raw)
    if not match:
        return None
    try:
        return date(*(int(value) for value in match.groups()))
    except ValueError:
        return None


_ENTITY_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fff（）()·]{2,100}?"
    r"(?:会计师事务所(?:（特殊普通合伙）|\(特殊普通合伙\))?"
    r"|律师事务所|清算事务(?:经纪)?有限公司|破产清算事务所|清算组))"
)


def _canonical_entity_name(raw: str, issuer: str) -> str:
    value = _compact(raw).strip("，,、及和与由")
    value = re.split(r"(?:指定|选定)", value)[-1]
    value = value.strip("，,、及和与由")
    value = re.sub(r"^经公开竞争", "", value)
    issuer_group = f"{issuer}清算组" if issuer else ""
    if issuer_group and issuer_group in value:
        return issuer_group
    if value in {"公司清算组", "本公司清算组", "清算组"} and issuer:
        return f"{issuer}清算组"
    return value


def _entity_type(name: str) -> AdministratorEntityType:
    if name.endswith("律师事务所"):
        return AdministratorEntityType.LAW_FIRM
    if "会计师事务所" in name:
        return AdministratorEntityType.ACCOUNTING_FIRM
    if name.endswith("清算组"):
        return AdministratorEntityType.LIQUIDATION_GROUP
    if "清算事务" in name or "破产清算事务所" in name:
        return AdministratorEntityType.LIQUIDATION_FIRM
    return AdministratorEntityType.OTHER


def _appointment_match(
    body_text: str,
    issuer: str = "",
) -> re.Match[str] | None:
    compact = _compact(body_text)
    pattern = re.compile(
        r"(?:指定|选定)(?P<names>[^。；;]{1,180}?)"
        r"(?P<link>共同担任|担任|为)"
        r"(?P<role>[^。；;]{0,50}?(?:临时管理人|管理人))"
    )
    matches = list(pattern.finditer(compact))
    if not matches:
        return None
    def score(item: re.Match[str]) -> tuple[int, int]:
        names = item.group("names")
        role = item.group("role")
        value = 0
        if issuer and issuer in role:
            value += 8
        if role.startswith(("公司", "本公司")):
            value += 5
        if issuer and issuer in names:
            value += 3
        if (
            re.search(r"[\u4e00-\u9fff]{2,40}(?:股份)?有限公司", role)
            and (not issuer or issuer not in role)
        ):
            value -= 8
        # At equal subject confidence, prefer the shorter explicit clause.
        return value, -len(item.group(0))
    return max(matches, key=score)


def _rejection(row: AnnouncementSourceRow, reason: str) -> ExtractionResult:
    rejection = ExtractionRejection(
        rejection_id=_stable_id("ARJ", row.announcement_id, reason),
        announcement_id=row.announcement_id,
        symbol=row.symbol,
        title=row.title,
        reason=reason,
    )
    return ExtractionResult(accepted=False, rejection=rejection)


def extract_administrator_appointment(row: AnnouncementSourceRow) -> ExtractionResult:
    """Extract one high-confidence appointment statement from an announcement."""
    if any(term in row.title for term in RELATED_ENTITY_TERMS):
        return _rejection(row, "related_entity_title")
    if not ("管理人" in row.title and any(term in row.title for term in ("指定", "选定"))):
        return _rejection(row, "title_not_explicit_appointment")
    if len(row.body_text.strip()) < 200:
        return _rejection(row, "body_missing_or_too_short")
    issuer = _issuer_name(row.body_text)
    match = _appointment_match(row.body_text, issuer)
    if match is None:
        return _rejection(row, "body_has_no_explicit_appointment_clause")

    names_blob = match.group("names")
    raw_entities = [item.group(1) for item in _ENTITY_PATTERN.finditer(names_blob)]
    entity_pairs: list[tuple[str, str]] = []
    for raw_name in raw_entities:
        name = _canonical_entity_name(raw_name, issuer)
        raw_alias = _compact(raw_name).strip("，,、及和与由")
        if name and name not in [item[1] for item in entity_pairs]:
            entity_pairs.append((raw_alias, name))
    canonical_names = [item[1] for item in entity_pairs]
    if not canonical_names:
        return _rejection(row, "administrator_entity_not_parseable")
    if any(name in {"公司清算组", "本公司清算组"} for name in canonical_names):
        return _rejection(row, "issuer_name_missing_for_liquidation_group")

    compact_body = _compact(row.body_text)
    quote_start = max(0, compact_body.rfind("。", 0, match.start()) + 1)
    quote_end_marker = compact_body.find("。", match.end())
    quote_end = quote_end_marker + 1 if quote_end_marker >= 0 else match.end()
    quote = compact_body[quote_start:quote_end][:600]
    decision_date = None
    for candidate in re.finditer(
        r"\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}日?",
        compact_body[max(0, match.start() - 240):match.start()],
    ):
        decision_date = _parse_date(candidate.group(0))
    effective_date = decision_date or row.announcement_date
    date_basis: Literal["decision_date_in_quote", "announcement_date"] = (
        "decision_date_in_quote" if decision_date else "announcement_date"
    )

    formal_title = (
        "裁定受理" in row.title
        or "重整被法院指定管理人" in row.title
        or ("法院指定管理人" in row.title and "预重整" not in row.title)
    )
    appointment_kind = (
        AppointmentKind.ADMINISTRATOR
        if formal_title and "临时管理人" not in match.group("role")
        else AppointmentKind.TEMPORARY_ADMINISTRATOR
    )
    participation_role = (
        ParticipationRole.JOINT
        if len(canonical_names) > 1 or match.group("link") == "共同担任"
        else ParticipationRole.SOLE
    )

    case_number = _canonical_case_number(row.body_text)
    identity_basis = (
        f"listed_company:{row.symbol}:application_case_number:{case_number}"
        if case_number
        else f"listed_company:{row.symbol}:announcement:{row.announcement_id}"
    )
    case_id = _stable_id("RCASE", identity_basis)
    document_id = f"cninfo:{row.announcement_id}"
    source_document = SourceDocument(
        document_id=document_id,
        announcement_id=row.announcement_id,
        symbol=row.symbol,
        title=row.title,
        source_name=row.source,
        source_url=row.url,
        published_date=row.announcement_date,
        published_at=row.published_at,
        body_sha256=hashlib.sha256(row.body_text.encode("utf-8")).hexdigest(),
        evidence_quote=quote,
    )
    case = RestructuringCase(
        case_id=case_id,
        symbol=row.symbol,
        official_case_number=case_number,
        identity_basis=identity_basis,
    )

    organizations: list[AdministratorOrganization] = []
    aliases: list[AdministratorAlias] = []
    assignments: list[AdministratorAssignment] = []
    events: list[RestructuringEvent] = []
    for raw_alias, canonical_name in entity_pairs:
        organization_id = _stable_id("AORG", canonical_name)
        organization = AdministratorOrganization(
            organization_id=organization_id,
            canonical_name=canonical_name,
            entity_type=_entity_type(canonical_name),
        )
        assignment_id = _stable_id(
            "AASN",
            case_id,
            organization_id,
            appointment_kind,
            effective_date,
            document_id,
        )
        assignment = AdministratorAssignment(
            assignment_id=assignment_id,
            case_id=case_id,
            organization_id=organization_id,
            appointment_kind=appointment_kind,
            participation_role=participation_role,
            effective_date=effective_date,
            effective_date_basis=date_basis,
            source_document_id=document_id,
        )
        event = RestructuringEvent(
            event_id=_stable_id("AEVT", assignment_id, "administrator_appointed"),
            case_id=case_id,
            assignment_id=assignment_id,
            event_type=RestructuringEventType.ADMINISTRATOR_APPOINTED,
            event_date=effective_date,
            information_available_date=row.announcement_date,
            source_document_id=document_id,
        )
        organizations.append(organization)
        if raw_alias in {"公司清算组", "本公司清算组"} and raw_alias != canonical_name:
            aliases.append(AdministratorAlias(
                alias_id=_stable_id(
                    "AALS", organization_id, raw_alias, document_id
                ),
                organization_id=organization_id,
                alias=raw_alias,
                source_document_id=document_id,
            ))
        assignments.append(assignment)
        events.append(event)

    return ExtractionResult(
        accepted=True,
        source_document=source_document,
        case=case,
        organizations=organizations,
        aliases=aliases,
        assignments=assignments,
        events=events,
    )


def classify_restructuring_milestone(
    title: str,
) -> RestructuringEventType | None:
    """Map an official listed-company title to one frozen milestone."""
    if any(term in title for term in RELATED_ENTITY_TERMS):
        return None
    if any(term in title for term in ("重整计划执行完毕", "重整程序终结", "执行完毕重整计划")):
        return RestructuringEventType.RESTRUCTURING_COMPLETED
    if any(term in title for term in ("终止预重整", "终止重整", "宣告破产")):
        return RestructuringEventType.RESTRUCTURING_TERMINATED
    if any(term in title for term in ("裁定批准重整计划", "批准公司重整计划", "法院批准重整计划")):
        return RestructuringEventType.RESTRUCTURING_PLAN_APPROVED
    if any(term in title for term in ("重整计划（草案）", "重整计划草案")):
        return RestructuringEventType.RESTRUCTURING_PLAN_PUBLISHED
    if (
        any(term in title for term in ("公开招募", "招募和遴选", "招募重整投资人"))
        and "重整投资人" in title
    ):
        return RestructuringEventType.INVESTOR_RECRUITMENT_STARTED
    if any(term in title for term in ("裁定受理公司重整", "法院受理公司重整", "裁定受理重整")):
        return RestructuringEventType.FORMAL_RESTRUCTURING_ACCEPTED
    if any(term in title for term in ("启动预重整", "预重整决定书", "受理预重整")):
        return RestructuringEventType.PRE_RESTRUCTURING_STARTED
    return None


def _rebind_case(
    result: ExtractionResult,
    canonical_case: RestructuringCase,
) -> ExtractionResult:
    """Bind a later notice to an earlier, explicit application case."""
    assignments: list[AdministratorAssignment] = []
    events: list[RestructuringEvent] = []
    for item in result.assignments:
        assignment_id = _stable_id(
            "AASN",
            canonical_case.case_id,
            item.organization_id,
            item.appointment_kind,
            item.effective_date,
            item.source_document_id,
        )
        assignment = item.model_copy(update={
            "assignment_id": assignment_id,
            "case_id": canonical_case.case_id,
        })
        assignments.append(assignment)
        events.append(RestructuringEvent(
            event_id=_stable_id("AEVT", assignment_id, "administrator_appointed"),
            case_id=canonical_case.case_id,
            assignment_id=assignment_id,
            event_type=RestructuringEventType.ADMINISTRATOR_APPOINTED,
            event_date=item.effective_date,
            information_available_date=result.source_document.published_date,
            source_document_id=item.source_document_id,
        ))
    return result.model_copy(update={
        "case": canonical_case,
        "assignments": assignments,
        "events": events,
    })


def _organization_identity_key(name: str) -> str:
    """Merge only legal-form suffix variants; branches remain independent."""
    return name.replace("（特殊普通合伙）", "").replace("(特殊普通合伙)", "")


def _rebind_organizations(
    result: ExtractionResult,
    canonical_by_key: dict[str, str],
) -> ExtractionResult:
    if not result.accepted or result.case is None or result.source_document is None:
        return result
    organization_by_old_id = {
        item.organization_id: item for item in result.organizations
    }
    organizations: list[AdministratorOrganization] = []
    aliases = list(result.aliases)
    assignments: list[AdministratorAssignment] = []
    events: list[RestructuringEvent] = []
    for item in result.assignments:
        old = organization_by_old_id[item.organization_id]
        canonical_name = canonical_by_key[
            _organization_identity_key(old.canonical_name)
        ]
        organization_id = _stable_id("AORG", canonical_name)
        organization = AdministratorOrganization(
            organization_id=organization_id,
            canonical_name=canonical_name,
            entity_type=_entity_type(canonical_name),
        )
        if organization not in organizations:
            organizations.append(organization)
        if old.canonical_name != canonical_name:
            aliases.append(AdministratorAlias(
                alias_id=_stable_id(
                    "AALS",
                    organization_id,
                    old.canonical_name,
                    result.source_document.document_id,
                ),
                organization_id=organization_id,
                alias=old.canonical_name,
                source_document_id=result.source_document.document_id,
            ))
        assignment_id = _stable_id(
            "AASN",
            item.case_id,
            organization_id,
            item.appointment_kind,
            item.effective_date,
            item.source_document_id,
        )
        assignment = item.model_copy(update={
            "assignment_id": assignment_id,
            "organization_id": organization_id,
        })
        assignments.append(assignment)
        events.append(RestructuringEvent(
            event_id=_stable_id("AEVT", assignment_id, "administrator_appointed"),
            case_id=item.case_id,
            assignment_id=assignment_id,
            event_type=RestructuringEventType.ADMINISTRATOR_APPOINTED,
            event_date=item.effective_date,
            information_available_date=result.source_document.published_date,
            source_document_id=item.source_document_id,
        ))
    unique_aliases = {item.alias_id: item for item in aliases}
    return result.model_copy(update={
        "organizations": organizations,
        "aliases": list(unique_aliases.values()),
        "assignments": assignments,
        "events": events,
    })


class AdministratorRepository:
    """SQLite append-only fact store; conflicting IDs fail closed."""

    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.executescript(
                """
                pragma journal_mode=wal;
                create table if not exists source_documents (
                    document_id text primary key,
                    symbol text not null,
                    published_date text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists restructuring_cases (
                    case_id text primary key,
                    symbol text not null,
                    official_case_number text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists administrator_organizations (
                    organization_id text primary key,
                    canonical_name text not null unique,
                    entity_type text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists administrator_aliases (
                    alias_id text primary key,
                    organization_id text not null,
                    alias text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists administrator_assignments (
                    assignment_id text primary key,
                    case_id text not null,
                    organization_id text not null,
                    appointment_kind text not null,
                    participation_role text not null,
                    effective_date text not null,
                    source_document_id text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists restructuring_events (
                    event_id text primary key,
                    case_id text not null,
                    assignment_id text not null,
                    event_type text not null,
                    event_date text not null,
                    information_available_date text not null,
                    source_document_id text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists extraction_rejections (
                    rejection_id text primary key,
                    announcement_id text not null,
                    symbol text not null,
                    reason text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists materialization_runs (
                    run_id text primary key,
                    payload_json text not null,
                    created_at text not null
                );
                create index if not exists idx_cases_symbol
                    on restructuring_cases(symbol);
                create index if not exists idx_assignments_case
                    on administrator_assignments(case_id);
                create index if not exists idx_assignments_org
                    on administrator_assignments(organization_id);
                create index if not exists idx_events_info_date
                    on restructuring_events(information_available_date);
                """
            )

    @staticmethod
    def _insert_immutable(
        connection: sqlite3.Connection,
        *,
        table: str,
        id_column: str,
        record_id: str,
        columns: dict[str, str],
        payload_json: str,
    ) -> bool:
        previous = connection.execute(
            f"select payload_json from {table} where {id_column}=?",
            (record_id,),
        ).fetchone()
        if previous:
            if str(previous[0]) != payload_json:
                raise ValueError(f"{table}.{record_id} 已冻结且 payload 冲突")
            return False
        created_at = datetime.now(timezone.utc).isoformat()
        all_columns = [id_column, *columns, "payload_json", "created_at"]
        placeholders = ",".join("?" for _ in all_columns)
        connection.execute(
            f"insert into {table} ({','.join(all_columns)}) values ({placeholders})",
            (record_id, *columns.values(), payload_json, created_at),
        )
        return True

    def persist(self, result: ExtractionResult) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            if not result.accepted:
                if result.rejection is None:
                    raise ValueError("rejected extraction 缺 rejection")
                item = result.rejection
                self._insert_immutable(
                    connection,
                    table="extraction_rejections",
                    id_column="rejection_id",
                    record_id=item.rejection_id,
                    columns={
                        "announcement_id": item.announcement_id,
                        "symbol": item.symbol,
                        "reason": item.reason,
                    },
                    payload_json=_payload(item),
                )
                return
            if result.source_document is None or result.case is None:
                raise ValueError("accepted extraction 缺 source_document/case")
            source = result.source_document
            self._insert_immutable(
                connection,
                table="source_documents",
                id_column="document_id",
                record_id=source.document_id,
                columns={
                    "symbol": source.symbol,
                    "published_date": source.published_date.isoformat(),
                },
                payload_json=_payload(source),
            )
            case = result.case
            self._insert_immutable(
                connection,
                table="restructuring_cases",
                id_column="case_id",
                record_id=case.case_id,
                columns={
                    "symbol": case.symbol,
                    "official_case_number": case.official_case_number,
                },
                payload_json=_payload(case),
            )
            for item in result.organizations:
                self._insert_immutable(
                    connection,
                    table="administrator_organizations",
                    id_column="organization_id",
                    record_id=item.organization_id,
                    columns={
                        "canonical_name": item.canonical_name,
                        "entity_type": item.entity_type.value,
                    },
                    payload_json=_payload(item),
                )
            for item in result.aliases:
                self._insert_immutable(
                    connection,
                    table="administrator_aliases",
                    id_column="alias_id",
                    record_id=item.alias_id,
                    columns={
                        "organization_id": item.organization_id,
                        "alias": item.alias,
                    },
                    payload_json=_payload(item),
                )
            for item in result.assignments:
                self._insert_immutable(
                    connection,
                    table="administrator_assignments",
                    id_column="assignment_id",
                    record_id=item.assignment_id,
                    columns={
                        "case_id": item.case_id,
                        "organization_id": item.organization_id,
                        "appointment_kind": item.appointment_kind.value,
                        "participation_role": item.participation_role.value,
                        "effective_date": item.effective_date.isoformat(),
                        "source_document_id": item.source_document_id,
                    },
                    payload_json=_payload(item),
                )
            for item in result.events:
                self._insert_immutable(
                    connection,
                    table="restructuring_events",
                    id_column="event_id",
                    record_id=item.event_id,
                    columns={
                        "case_id": item.case_id,
                        "assignment_id": item.assignment_id,
                        "event_type": item.event_type,
                        "event_date": item.event_date.isoformat(),
                        "information_available_date": item.information_available_date.isoformat(),
                        "source_document_id": item.source_document_id,
                    },
                    payload_json=_payload(item),
                )

    def persist_run(self, summary: MaterializationSummary) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            self._insert_immutable(
                connection,
                table="materialization_runs",
                id_column="run_id",
                record_id=summary.run_id,
                columns={},
                payload_json=_payload(summary),
            )

    def persist_milestone_event(
        self,
        source: SourceDocument,
        event: RestructuringEvent,
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            existing_source = connection.execute(
                "select 1 from source_documents where document_id=?",
                (source.document_id,),
            ).fetchone()
            if existing_source is None:
                self._insert_immutable(
                    connection,
                    table="source_documents",
                    id_column="document_id",
                    record_id=source.document_id,
                    columns={
                        "symbol": source.symbol,
                        "published_date": source.published_date.isoformat(),
                    },
                    payload_json=_payload(source),
                )
            self._insert_immutable(
                connection,
                table="restructuring_events",
                id_column="event_id",
                record_id=event.event_id,
                columns={
                    "case_id": event.case_id,
                    "assignment_id": event.assignment_id,
                    "event_type": event.event_type.value,
                    "event_date": event.event_date.isoformat(),
                    "information_available_date": (
                        event.information_available_date.isoformat()
                    ),
                    "source_document_id": event.source_document_id,
                },
                payload_json=_payload(event),
            )

    def status(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {
                "contract_version": CONTRACT_VERSION,
                "database": str(self.path),
                "status": "missing",
            }
        try:
            with sqlite3.connect(
                f"file:{self.path}?mode=ro", uri=True
            ) as connection:
                counts = {
                    table: int(
                        connection.execute(
                            f"select count(*) from {table}"
                        ).fetchone()[0]
                    )
                    for table in (
                        "source_documents",
                        "restructuring_cases",
                        "administrator_organizations",
                        "administrator_aliases",
                        "administrator_assignments",
                        "restructuring_events",
                        "extraction_rejections",
                        "materialization_runs",
                    )
                }
                bounds = connection.execute(
                    "select min(information_available_date),"
                    "max(information_available_date) from restructuring_events"
                ).fetchone()
        except sqlite3.Error as exc:
            return {
                "contract_version": CONTRACT_VERSION,
                "database": str(self.path),
                "status": "invalid",
                "error": str(exc),
            }
        return {
            "contract_version": CONTRACT_VERSION,
            "database": str(self.path),
            "status": "ready" if counts["administrator_assignments"] else "empty",
            "counts": counts,
            "event_information_window": {
                "start": str(bounds[0] or ""),
                "end": str(bounds[1] or ""),
            },
        }

    def assignments_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                select a.assignment_id,a.case_id,a.organization_id,
                       a.appointment_kind,a.participation_role,a.effective_date,
                       o.canonical_name,o.entity_type,
                       e.event_id,e.event_date,e.information_available_date,
                       d.document_id,d.published_date,d.payload_json as document_payload
                from administrator_assignments a
                join restructuring_cases c on c.case_id=a.case_id
                join administrator_organizations o on o.organization_id=a.organization_id
                join restructuring_events e on e.assignment_id=a.assignment_id
                join source_documents d on d.document_id=a.source_document_id
                where c.symbol=? and e.event_type='administrator_appointed'
                order by e.information_available_date,a.appointment_kind,o.canonical_name
                """,
                (symbol,),
            ).fetchall()
        return [
            {
                **dict(row),
                "source_document": json.loads(str(row["document_payload"])),
            }
            for row in rows
        ]

    def events_for_organization(self, organization_id: str) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                select e.event_id,e.case_id,e.assignment_id,e.event_date,
                       e.information_available_date,e.event_type,a.appointment_kind,
                       a.participation_role,c.symbol,o.canonical_name
                from restructuring_events e
                join administrator_assignments a on a.assignment_id=e.assignment_id
                join restructuring_cases c on c.case_id=e.case_id
                join administrator_organizations o on o.organization_id=a.organization_id
                where a.organization_id=?
                order by e.information_available_date,c.symbol,e.event_id
                """,
                (organization_id,),
            ).fetchall()
        return [dict(row) for row in rows]


def _load_milestone_announcements(
    source_database: Path,
    *,
    symbols: set[str],
    start_date: date | None,
    through: date | None,
) -> list[AnnouncementSourceRow]:
    if not symbols:
        return []
    placeholders = ",".join("?" for _ in symbols)
    where = [f"symbol in ({placeholders})", "title like '%重整%'"]
    parameters: list[Any] = [*sorted(symbols)]
    if start_date:
        where.append("announcement_date>=?")
        parameters.append(start_date.isoformat())
    if through:
        where.append("announcement_date<=?")
        parameters.append(through.isoformat())
    with sqlite3.connect(f"file:{source_database}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "select announcement_id,symbol,announcement_date,"
            "coalesce(published_at,''),title,coalesce(url,''),"
            "coalesce(body_text,''),source from company_announcements where "
            + " and ".join(where)
            + " order by announcement_date,announcement_id",
            parameters,
        ).fetchall()
    return [
        AnnouncementSourceRow(
            announcement_id=str(row[0]),
            symbol=str(row[1]),
            announcement_date=date.fromisoformat(str(row[2])[:10]),
            published_at=str(row[3]),
            title=str(row[4]),
            url=str(row[5]),
            body_text=str(row[6]),
            source=str(row[7]),
        )
        for row in rows
    ]


def _materialize_case_milestones(
    *,
    repository: AdministratorRepository,
    source_database: Path,
    accepted_results: list[ExtractionResult],
    start_date: date | None,
    through: date | None,
) -> set[str]:
    cases_by_symbol: dict[str, RestructuringCase] = {}
    assignments_by_symbol: dict[str, dict[str, AdministratorAssignment]] = {}
    for result in accepted_results:
        if not result.accepted or result.case is None:
            continue
        cases_by_symbol[result.case.symbol] = result.case
        current = assignments_by_symbol.setdefault(result.case.symbol, {})
        current.update({item.assignment_id: item for item in result.assignments})
    rows = _load_milestone_announcements(
        source_database,
        symbols=set(cases_by_symbol),
        start_date=start_date,
        through=through,
    )
    earliest: dict[
        tuple[str, RestructuringEventType],
        AnnouncementSourceRow,
    ] = {}
    for row in rows:
        event_type = classify_restructuring_milestone(row.title)
        if event_type is None:
            continue
        key = (row.symbol, event_type)
        earliest.setdefault(key, row)

    event_ids: set[str] = set()
    for (symbol, event_type), row in earliest.items():
        eligible = [
            item for item in assignments_by_symbol.get(symbol, {}).values()
            if item.effective_date <= row.announcement_date
        ]
        if not eligible:
            continue
        preferred_kind = (
            AppointmentKind.TEMPORARY_ADMINISTRATOR
            if event_type == RestructuringEventType.PRE_RESTRUCTURING_STARTED
            else AppointmentKind.ADMINISTRATOR
        )
        preferred = [
            item for item in eligible if item.appointment_kind == preferred_kind
        ]
        pool = preferred or eligible
        latest_date = max(item.effective_date for item in pool)
        selected_by_organization: dict[str, AdministratorAssignment] = {}
        for item in sorted(pool, key=lambda candidate: candidate.assignment_id):
            if item.effective_date == latest_date:
                selected_by_organization.setdefault(item.organization_id, item)
        selected = list(selected_by_organization.values())
        case = cases_by_symbol[symbol]
        document_id = f"cninfo:{row.announcement_id}"
        source = SourceDocument(
            document_id=document_id,
            announcement_id=row.announcement_id,
            symbol=symbol,
            title=row.title,
            source_name=row.source,
            source_url=row.url,
            published_date=row.announcement_date,
            published_at=row.published_at,
            body_sha256=hashlib.sha256(
                (row.body_text or row.title).encode("utf-8")
            ).hexdigest(),
            evidence_quote=row.title,
        )
        for assignment in selected:
            event = RestructuringEvent(
                event_id=_stable_id(
                    "AEVT",
                    case.case_id,
                    assignment.organization_id,
                    event_type,
                    row.announcement_date,
                ),
                case_id=case.case_id,
                assignment_id=assignment.assignment_id,
                event_type=event_type,
                event_date=row.announcement_date,
                information_available_date=row.announcement_date,
                source_document_id=document_id,
            )
            repository.persist_milestone_event(source, event)
            event_ids.add(event.event_id)
    return event_ids


def load_candidate_announcements(
    source_database: Path,
    *,
    start_date: date | None = None,
    through: date | None = None,
    limit: int = 0,
    body_cache_dir: Path | None = None,
) -> list[AnnouncementSourceRow]:
    """Read the conservative listed-company appointment candidate slice."""
    where = [
        "title like '%管理人%'",
        "(title like '%指定%' or title like '%选定%')",
    ]
    parameters: list[Any] = []
    if start_date:
        where.append("announcement_date>=?")
        parameters.append(start_date.isoformat())
    if through:
        where.append("announcement_date<=?")
        parameters.append(through.isoformat())
    query = (
        "select announcement_id,symbol,announcement_date,"
        "coalesce(published_at,''),title,coalesce(url,''),"
        "coalesce(body_text,''),source "
        "from company_announcements where "
        + " and ".join(where)
        + " order by announcement_date,announcement_id"
    )
    if limit:
        query += " limit ?"
        parameters.append(limit)
    with sqlite3.connect(f"file:{source_database}?mode=ro", uri=True) as connection:
        rows = connection.execute(query, parameters).fetchall()
    candidates: list[AnnouncementSourceRow] = []
    for row in rows:
        body_text = str(row[6] or "")
        source = str(row[7])
        if not body_text.strip() and body_cache_dir is not None:
            cache_path = (
                body_cache_dir / str(row[0])[:4] / f"{row[0]}.json"
            )
            if cache_path.is_file():
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    cached = {}
                if (
                    str(cached.get("announcement_id") or "") == str(row[0])
                    and str(cached.get("announcement_date") or "")[:10]
                    == str(row[2])[:10]
                    and isinstance(cached.get("text"), str)
                ):
                    body_text = str(cached["text"])
                    source = "cninfo_pdf_cache"
        if not body_text.strip():
            continue
        candidates.append(AnnouncementSourceRow(
            announcement_id=str(row[0]),
            symbol=str(row[1]),
            announcement_date=date.fromisoformat(str(row[2])[:10]),
            published_at=str(row[3] or ""),
            title=str(row[4]),
            url=str(row[5] or ""),
            body_text=body_text,
            source=source,
        ))
    return candidates


def materialize_administrator_facts(
    *,
    source_database: Path,
    database: Path,
    start_date: date | None = None,
    through: date | None = None,
    limit: int = 0,
    body_cache_dir: Path | None = None,
) -> MaterializationSummary:
    rows = load_candidate_announcements(
        source_database,
        start_date=start_date,
        through=through,
        limit=limit,
        body_cache_dir=body_cache_dir,
    )
    repository = AdministratorRepository(database)
    accepted = rejected = 0
    organizations: set[str] = set()
    assignments: set[str] = set()
    events: set[str] = set()
    latest_case_by_symbol: dict[str, tuple[RestructuringCase, date]] = {}
    case_by_number: dict[tuple[str, str], RestructuringCase] = {}
    accepted_results: list[ExtractionResult] = []
    extracted = [(row, extract_administrator_appointment(row)) for row in rows]
    names_by_key: dict[str, set[str]] = {}
    for _, result in extracted:
        for organization in result.organizations:
            names_by_key.setdefault(
                _organization_identity_key(organization.canonical_name),
                set(),
            ).add(organization.canonical_name)
    canonical_by_key = {
        key: max(names, key=lambda name: (len(name), name))
        for key, names in names_by_key.items()
    }
    for row, raw_result in extracted:
        result = _rebind_organizations(raw_result, canonical_by_key)
        if result.accepted and result.case is not None:
            extracted_case = result.case
            numbered = (
                case_by_number.get((row.symbol, extracted_case.official_case_number))
                if extracted_case.official_case_number else None
            )
            previous = latest_case_by_symbol.get(row.symbol)
            nearby = (
                previous[0]
                if previous
                and (row.announcement_date - previous[1]).days <= 1200
                and not extracted_case.official_case_number
                else None
            )
            canonical_case = numbered or nearby or extracted_case
            if canonical_case.case_id != extracted_case.case_id:
                result = _rebind_case(result, canonical_case)
            latest_case_by_symbol[row.symbol] = (canonical_case, row.announcement_date)
            if canonical_case.official_case_number:
                case_by_number[
                    (row.symbol, canonical_case.official_case_number)
                ] = canonical_case
        repository.persist(result)
        if result.accepted:
            accepted += 1
            accepted_results.append(result)
            organizations.update(item.organization_id for item in result.organizations)
            assignments.update(item.assignment_id for item in result.assignments)
            events.update(item.event_id for item in result.events)
        else:
            rejected += 1
    events.update(_materialize_case_milestones(
        repository=repository,
        source_database=source_database,
        accepted_results=accepted_results,
        start_date=start_date,
        through=through,
    ))
    summary = MaterializationSummary(
        run_id=f"AMR-{uuid4().hex.upper()}",
        source_database=str(source_database),
        database=str(database),
        start_date=start_date,
        through=through,
        candidates_scanned=len(rows),
        documents_accepted=accepted,
        documents_rejected=rejected,
        organizations_seen=len(organizations),
        assignments_seen=len(assignments),
        events_seen=len(events),
        generated_at=datetime.now(timezone.utc),
    )
    repository.persist_run(summary)
    return summary
