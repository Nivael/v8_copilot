"""Deterministic P7 announcement taxonomy, evidence bundles and issuer transitions."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from valuation_episodes import classify_official_title


CONTRACT_VERSION = "p7_announcement_intelligence_v1"
CATEGORIES = (
    "restructuring_and_pre_restructuring",
    "risk_warning_and_delisting",
    "control_and_ownership",
    "litigation_guarantee_occupation",
    "audit_and_financial_reporting",
    "asset_and_major_transaction",
    "operations_and_production",
    "capital_structure_and_shareholder",
    "regulatory_and_discipline",
    "routine_or_other",
)

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("restructuring_and_pre_restructuring", ("预重整", "重整", "破产", "债权人会议", "重整投资人")),
    ("risk_warning_and_delisting", ("风险警示", "撤销退市风险", "撤销其他风险", "终止上市", "退市整理", "摘牌")),
    ("control_and_ownership", ("控制权", "实际控制人", "司法拍卖", "权益变动", "表决权委托")),
    ("litigation_guarantee_occupation", ("诉讼", "仲裁", "担保", "资金占用", "追偿")),
    ("audit_and_financial_reporting", ("年度报告", "季度报告", "半年度报告", "业绩预告", "审计意见", "会计差错", "财务报告")),
    ("asset_and_major_transaction", ("重大资产", "资产重组", "资产出售", "资产收购", "资产处置", "重大交易")),
    ("operations_and_production", ("停产", "复产", "生产经营", "重大合同", "许可证", "经营异常")),
    ("capital_structure_and_shareholder", ("增持", "减持", "回购", "解禁", "股本", "股份冻结", "股份质押", "限售")),
    ("regulatory_and_discipline", ("立案", "处罚", "问询函", "关注函", "监管函", "纪律处分", "整改")),
)

PROGRESS_TERMS = ("进展", "提示性", "风险提示", "进度", "尚未", "可能被", "申请")
JUDGMENT_CHANGE_TERMS = (
    "裁定", "不予受理", "驳回", "签署重整投资协议", "终止重整投资协议",
    "重整计划草案", "出资人权益调整", "债权申报", "控制权", "实际控制人",
    "资金占用", "违规担保", "审计意见", "无法表示", "保留意见", "否定意见",
    "会计差错", "重大资产", "停产", "复产", "立案调查", "行政处罚",
    "纪律处分", "终止上市决定", "退市整理期",
)
HARD_EVENT_RULES: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("court_restructuring_accepted", ("裁定受理公司重整", "法院受理公司重整", "裁定受理重整"), "restructuring", "formal_restructuring_accepted"),
    ("court_restructuring_rejected", ("不予受理重整", "驳回重整申请", "不受理重整申请"), "restructuring", "restructuring_rejected"),
    ("restructuring_terminated", ("终止预重整", "终止重整程序", "终结预重整", "终结重整程序"), "restructuring", "terminated"),
    ("investor_agreement_signed", ("签署重整投资协议", "重整投资协议签署", "签订重整投资协议"), "restructuring", "investor_agreement_signed"),
    ("investor_agreement_terminated", ("解除重整投资协议", "终止重整投资协议"), "restructuring", "investor_agreement_terminated"),
    ("restructuring_plan_approved", ("裁定批准重整计划", "法院批准重整计划", "批准公司重整计划"), "restructuring", "plan_approved"),
    ("restructuring_plan_rejected", ("不批准重整计划", "驳回重整计划"), "restructuring", "plan_rejected"),
    ("control_change_completed", ("控制权变更完成", "实际控制人变更完成", "完成过户暨控制权变更"), "control", "control_changed"),
    ("risk_warning_removed", ("撤销退市风险警示", "撤销其他风险警示", "撤销风险警示"), "risk_warning", "removed"),
    ("delisting_decision", ("终止上市决定", "决定终止公司股票上市"), "risk_warning", "delisting_decided"),
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AnnouncementFact(StrictModel):
    announcement_id: str
    symbol: str = Field(pattern=r"^\d{6}$")
    announcement_date: str
    available_as_of: str
    title: str
    url: str = ""
    source: str
    body_available: bool = False
    category: Literal[
        "restructuring_and_pre_restructuring", "risk_warning_and_delisting",
        "control_and_ownership", "litigation_guarantee_occupation",
        "audit_and_financial_reporting", "asset_and_major_transaction",
        "operations_and_production", "capital_structure_and_shareholder",
        "regulatory_and_discipline", "routine_or_other",
    ]
    classification_basis: str
    hard_event_type: str = ""
    hard_dimension: str = ""
    hard_to_state: str = ""
    not_hard_outcome: bool = True
    priority_reasons: list[str] = Field(default_factory=list)
    llm_route: Literal[
        "not_required", "deterministic_hard_fact", "shortlist_body_available",
        "shortlist_body_missing",
    ] = "not_required"


class AnnouncementBundle(StrictModel):
    bundle_id: str = Field(pattern=r"^P7AB-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    announcement_date: str
    category: str
    topic_key: str
    announcement_ids: list[str]
    titles: list[str]
    source_urls: list[str]
    hard_event_types: list[str]
    priority_reasons: list[str]
    conflict_status: Literal["clear", "conflicted"]


class IssuerTransition(StrictModel):
    transition_id: str = Field(pattern=r"^P7TR-[A-F0-9]{20}$")
    symbol: str = Field(pattern=r"^\d{6}$")
    dimension: str
    from_state: str
    to_state: str
    event_type: str
    announced_at: str
    effective_at: str
    available_as_of: str
    bundle_id: str
    source_refs: list[str]
    evidence_status: Literal["verified", "provisional", "conflicted"]
    conflict_reason: str = ""
    not_hard_outcome: bool = False


class AnnouncementRun(StrictModel):
    run_id: str = Field(pattern=r"^P7AN-[A-F0-9]{20}$")
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    generated_at: str
    start_date: str
    through: str
    announcement_count: int = Field(ge=0)
    bundle_count: int = Field(ge=0)
    priority_bundle_count: int = Field(ge=0)
    hard_transition_count: int = Field(ge=0)
    category_counts: dict[str, int]
    llm_route_counts: dict[str, int] = Field(default_factory=dict)
    facts: list[AnnouncementFact]
    bundles: list[AnnouncementBundle]
    transitions: list[IssuerTransition]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _id(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{_digest(parts)[:20].upper()}"


def _iso(value: Any) -> str:
    return date.fromisoformat(str(value)[:10]).isoformat()


def classify_announcement(title: str, announcement_type: str = "") -> tuple[str, str]:
    text = f"{announcement_type} {title}".strip()
    for category, terms in CATEGORY_RULES:
        term = next((item for item in terms if item in text), "")
        if term:
            return category, f"deterministic_term:{term}"
    return "routine_or_other", "fallback:no_deterministic_term"


def classify_hard_event(title: str) -> tuple[str, str, str]:
    normalized = re.sub(r"[ \t\n（）()《》]", "", title)
    for event_type, terms, dimension, to_state in HARD_EVENT_RULES:
        if any(re.sub(r"[ \t\n（）()《》]", "", term) in normalized for term in terms):
            if event_type == "risk_warning_removed" and any(term in title for term in ("申请", "可能", "尚需")):
                continue
            return event_type, dimension, to_state
    return "", "", ""


def _topic_key(title: str) -> str:
    text = re.sub(r"^(关于|公司关于)", "", title)
    text = re.sub(r"(的公告|公告|提示性公告|进展公告|补充公告|更正公告)$", "", text)
    text = re.sub(r"第[一二三四五六七八九十\d]+次", "", text)
    text = re.sub(r"[：:（）()\s]", "", text)
    return text[:36] or "other"


def load_announcements(
    *, base_database: Path, refresh_directory: Path,
    start_date: str, through: str,
) -> list[dict[str, Any]]:
    start, end = _iso(start_date), _iso(through)
    if not base_database.is_file():
        raise FileNotFoundError(base_database)
    with sqlite3.connect(f"file:{base_database}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "select announcement_id,symbol,announcement_date,title,"
            "coalesce(announcement_type,''),coalesce(url,''),source,"
            "case when body_text is not null and length(trim(body_text))>0 then 1 else 0 end "
            "from company_announcements where announcement_date between ? and ?",
            (start, end),
        ).fetchall()
    merged = {
        str(row[0]): {
            "announcement_id": str(row[0]), "symbol": str(row[1]),
            "announcement_date": str(row[2])[:10], "title": str(row[3]),
            "announcement_type": str(row[4]), "url": str(row[5]),
            "source": str(row[6]), "body_available": bool(row[7]),
        }
        for row in rows if row[0] and row[1] and row[2] and row[3]
    }
    if refresh_directory.is_dir():
        for path in sorted(refresh_directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("source") != "cninfo":
                continue
            for raw in payload.get("records") or []:
                day = str(raw.get("announcement_date") or "")[:10]
                if not start <= day <= end:
                    continue
                announcement_id = str(raw.get("announcement_id") or "")
                symbol = str(raw.get("symbol") or payload.get("symbol") or "")
                title = str(raw.get("title") or "").strip()
                if not announcement_id or len(symbol) != 6 or not title:
                    continue
                prior = merged.get(announcement_id, {})
                merged[announcement_id] = {
                    **prior,
                    "announcement_id": announcement_id,
                    "symbol": symbol,
                    "announcement_date": day,
                    "title": title,
                    "announcement_type": str(raw.get("announcement_type") or prior.get("announcement_type") or ""),
                    "url": str(raw.get("url") or raw.get("pdf_url") or prior.get("url") or ""),
                    "source": "cninfo_local_refresh",
                    "body_available": bool(str(raw.get("body_text") or "").strip()) or bool(prior.get("body_available")),
                }
    return sorted(merged.values(), key=lambda item: (item["announcement_date"], item["symbol"], item["announcement_id"]))


def build_announcement_run(
    *, base_database: Path, refresh_directory: Path,
    start_date: str, through: str,
    valuation_facts_database: Path | None = None,
    market_context_database: Path | None = None,
) -> AnnouncementRun:
    rows = load_announcements(
        base_database=base_database, refresh_directory=refresh_directory,
        start_date=start_date, through=through,
    )
    membership_dates: list[str] = []
    membership_by_date: dict[str, set[str]] = {}
    if market_context_database is not None and market_context_database.is_file():
        with sqlite3.connect(f"file:{market_context_database}?mode=ro", uri=True) as connection:
            member_rows = connection.execute(
                "select m.trade_date,m.symbol from st_membership_daily m "
                "where m.trade_date between ? and ? and exists ("
                "select 1 from benchmark_daily b where b.benchmark_id='csi_all_share' "
                "and b.trade_date=m.trade_date) order by m.trade_date,m.symbol",
                (_iso(start_date), _iso(through)),
            ).fetchall()
        for member_day, member_symbol in member_rows:
            membership_by_date.setdefault(str(member_day), set()).add(str(member_symbol))
        membership_dates = sorted(membership_by_date)

        def was_member(symbol: str, announcement_date: str) -> bool:
            position = bisect_right(membership_dates, announcement_date) - 1
            return position >= 0 and symbol in membership_by_date[membership_dates[position]]

        rows = [row for row in rows if was_member(row["symbol"], row["announcement_date"])]
    else:
        def was_member(symbol: str, announcement_date: str) -> bool:
            return True
    facts: list[AnnouncementFact] = []
    for row in rows:
        category, basis = classify_announcement(row["title"], row["announcement_type"])
        hard_type, dimension, to_state = classify_hard_event(row["title"])
        progress_only = bool(any(term in row["title"] for term in PROGRESS_TERMS) and not hard_type)
        reasons: list[str] = []
        if hard_type:
            reasons.append("hard_state_transition")
        if any(term in row["title"] for term in JUDGMENT_CHANGE_TERMS):
            reasons.append("may_change_research_judgment")
        if hard_type:
            llm_route = "deterministic_hard_fact"
        elif reasons and row["body_available"]:
            llm_route = "shortlist_body_available"
        elif reasons:
            llm_route = "shortlist_body_missing"
        else:
            llm_route = "not_required"
        facts.append(AnnouncementFact(
            announcement_id=row["announcement_id"], symbol=row["symbol"],
            announcement_date=row["announcement_date"], available_as_of=row["announcement_date"],
            title=row["title"], url=row["url"], source=row["source"],
            body_available=row["body_available"], category=category, classification_basis=basis,
            hard_event_type=hard_type, hard_dimension=dimension, hard_to_state=to_state,
            not_hard_outcome=not bool(hard_type) or progress_only,
            priority_reasons=sorted(set(reasons)),
            llm_route=llm_route,
        ))
    grouped: dict[tuple[str, str, str, str], list[AnnouncementFact]] = defaultdict(list)
    for fact in facts:
        grouped[(fact.symbol, fact.announcement_date, fact.category, _topic_key(fact.title))].append(fact)
    bundles: list[AnnouncementBundle] = []
    fact_to_bundle: dict[str, str] = {}
    for (symbol, day, category, topic), members in sorted(grouped.items()):
        hard_types = sorted({item.hard_event_type for item in members if item.hard_event_type})
        target_states = {item.hard_to_state for item in members if item.hard_to_state}
        conflicted = len(target_states) > 1
        bundle = AnnouncementBundle(
            bundle_id=_id("P7AB", symbol, day, category, topic, [item.announcement_id for item in members]),
            symbol=symbol, announcement_date=day, category=category, topic_key=topic,
            announcement_ids=[item.announcement_id for item in members],
            titles=[item.title for item in members],
            source_urls=sorted({item.url for item in members if item.url}),
            hard_event_types=hard_types,
            priority_reasons=sorted({reason for item in members for reason in item.priority_reasons}),
            conflict_status="conflicted" if conflicted else "clear",
        )
        bundles.append(bundle)
        for item in members:
            fact_to_bundle[item.announcement_id] = bundle.bundle_id

    transitions: list[IssuerTransition] = []
    state: dict[tuple[str, str], str] = {}
    seen_bundle_events: set[tuple[str, str]] = set()
    for fact in sorted(facts, key=lambda item: (item.available_as_of, item.announcement_id)):
        if not fact.hard_event_type or fact.not_hard_outcome:
            continue
        bundle_id = fact_to_bundle[fact.announcement_id]
        bundle = next(item for item in bundles if item.bundle_id == bundle_id)
        event_key = (bundle_id, fact.hard_event_type)
        if event_key in seen_bundle_events:
            continue
        seen_bundle_events.add(event_key)
        key = (fact.symbol, fact.hard_dimension)
        previous = state.get(key, "unknown")
        conflicted = bundle.conflict_status == "conflicted"
        if not conflicted and previous == fact.hard_to_state:
            continue
        transition = IssuerTransition(
            transition_id=_id("P7TR", fact.symbol, fact.hard_dimension, fact.available_as_of, fact.hard_event_type, bundle_id),
            symbol=fact.symbol, dimension=fact.hard_dimension,
            from_state=previous, to_state=fact.hard_to_state,
            event_type=fact.hard_event_type,
            announced_at=fact.announcement_date,
            effective_at=fact.announcement_date,
            available_as_of=fact.available_as_of,
            bundle_id=bundle_id,
            source_refs=[f"official_announcement:{fact.announcement_id}"],
            evidence_status="conflicted" if conflicted else "verified",
            conflict_reason="同一 evidence bundle 存在多个目标状态" if conflicted else "",
        )
        transitions.append(transition)
        if not conflicted:
            state[key] = fact.hard_to_state

    if valuation_facts_database is not None and valuation_facts_database.is_file():
        with sqlite3.connect(f"file:{valuation_facts_database}?mode=ro", uri=True) as connection:
            audit_rows = connection.execute(
                "select fact_id,symbol,available_date,payload_json from audit_opinion_facts "
                "where available_date<=? order by symbol,available_date,period_end",
                (_iso(through),),
            ).fetchall()
        prior_audit: dict[str, str] = {}
        for fact_id, symbol, available_date, payload_json in audit_rows:
            payload = json.loads(payload_json)
            current = str(payload.get("result") or "").strip()
            if not current:
                continue
            previous = prior_audit.get(str(symbol), "unknown")
            prior_audit[str(symbol)] = current
            if previous == "unknown" or previous == current or str(available_date) < _iso(start_date):
                continue
            if not was_member(str(symbol), str(available_date)):
                continue
            title = f"审计意见由{previous}变更为{current}"
            bundle = AnnouncementBundle(
                bundle_id=_id("P7AB", symbol, available_date, "audit_opinion_change", fact_id),
                symbol=str(symbol), announcement_date=str(available_date),
                category="audit_and_financial_reporting", topic_key="audit_opinion_change",
                announcement_ids=[str(fact_id)], titles=[title], source_urls=[],
                hard_event_types=["audit_opinion_changed"],
                priority_reasons=["hard_state_transition", "may_change_research_judgment"],
                conflict_status="clear",
            )
            bundles.append(bundle)
            transitions.append(IssuerTransition(
                transition_id=_id("P7TR", symbol, "audit_opinion", available_date, fact_id),
                symbol=str(symbol), dimension="audit_opinion", from_state=previous,
                to_state=current, event_type="audit_opinion_changed",
                announced_at=str(available_date), effective_at=str(available_date),
                available_as_of=str(available_date), bundle_id=bundle.bundle_id,
                source_refs=[str(payload.get("source_ref") or f"valuation_fact:{fact_id}")],
                evidence_status="verified",
            ))
        bundles.sort(key=lambda item: (item.announcement_date, item.symbol, item.bundle_id))
        transitions.sort(key=lambda item: (item.available_as_of, item.symbol, item.transition_id))

    identity = {
        "contract_version": CONTRACT_VERSION,
        "start_date": _iso(start_date), "through": _iso(through),
        "facts": [item.model_dump(mode="json") for item in facts],
        "bundles": [item.model_dump(mode="json") for item in bundles],
        "transitions": [item.model_dump(mode="json") for item in transitions],
    }
    return AnnouncementRun(
        run_id=_id("P7AN", identity),
        generated_at=datetime.now(timezone.utc).isoformat(),
        start_date=_iso(start_date), through=_iso(through),
        announcement_count=len(facts), bundle_count=len(bundles),
        priority_bundle_count=sum(bool(item.priority_reasons) for item in bundles),
        hard_transition_count=len(transitions),
        category_counts=dict(Counter(item.category for item in facts)),
        llm_route_counts=dict(Counter(item.llm_route for item in facts)),
        facts=facts, bundles=bundles, transitions=transitions,
    )


class AnnouncementIntelligenceRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.executescript("""
            create table if not exists announcement_runs (
                run_id text primary key, contract_version text not null,
                start_date text not null, through text not null,
                summary_json text not null, created_at text not null
            );
            create table if not exists announcement_facts (
                run_id text not null, announcement_id text not null,
                symbol text not null, available_as_of text not null,
                payload_json text not null, primary key(run_id,announcement_id)
            );
            create table if not exists announcement_bundles (
                run_id text not null, bundle_id text not null,
                symbol text not null, announcement_date text not null,
                payload_json text not null, primary key(run_id,bundle_id)
            );
            create table if not exists issuer_transitions (
                run_id text not null, transition_id text not null,
                symbol text not null, available_as_of text not null,
                payload_json text not null, primary key(run_id,transition_id)
            );
        """)
        return connection

    def store(self, run: AnnouncementRun) -> None:
        summary = run.model_dump(mode="json", exclude={"facts", "bundles", "transitions", "generated_at"})
        with self._connect() as connection:
            existing = connection.execute("select summary_json from announcement_runs where run_id=?", (run.run_id,)).fetchone()
            if existing is not None and json.loads(existing[0]) != summary:
                raise ValueError("P7 announcement run ID 已绑定不同内容")
            connection.execute(
                "insert or ignore into announcement_runs values (?,?,?,?,?,?)",
                (run.run_id, CONTRACT_VERSION, run.start_date, run.through, _canonical(summary), run.generated_at),
            )
            connection.executemany(
                "insert or ignore into announcement_facts values (?,?,?,?,?)",
                [(run.run_id, item.announcement_id, item.symbol, item.available_as_of, _canonical(item.model_dump(mode="json"))) for item in run.facts],
            )
            connection.executemany(
                "insert or ignore into announcement_bundles values (?,?,?,?,?)",
                [(run.run_id, item.bundle_id, item.symbol, item.announcement_date, _canonical(item.model_dump(mode="json"))) for item in run.bundles],
            )
            connection.executemany(
                "insert or ignore into issuer_transitions values (?,?,?,?,?)",
                [(run.run_id, item.transition_id, item.symbol, item.available_as_of, _canonical(item.model_dump(mode="json"))) for item in run.transitions],
            )

    def latest_run_id(self) -> str:
        if not self.path.is_file():
            return ""
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            row = connection.execute("select run_id from announcement_runs order by created_at desc limit 1").fetchone()
        return str(row[0]) if row else ""
