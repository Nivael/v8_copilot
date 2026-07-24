"""Read-only Tushare feasibility probe for the P6B historical market map."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import TushareHttpClient
from market_factors import normalize_market_cap_rows
from settings import DATA_ROOT, MARKET_CONTEXT_DB


CONTRACT_VERSION = "v8_p6b_provider_probe_v1"
SOURCE_DRY_PLAN_ID = "P6B0-BE1B382B7CF794EBAECA"
MARKET_CAP_COVERAGE_GATE = 0.95
FROZEN_PROBE_DATES = (
    "2016-08-09",
    "2019-04-04",
    "2021-03-09",
    "2021-03-25",
    "2022-04-20",
    "2023-07-19",
    "2023-10-12",
    "2024-04-29",
    "2025-04-30",
    "2026-01-15",
    "2026-07-17",
)
CAPITAL_PROBE_EPISODE_IDS = (
    "episode:SH600654:capital_structure_adjustment_path:2022-05-06:"
    "b5c27586e3ee",
    "episode:SZ000525:capital_structure_adjustment_path:2024-09-19:"
    "a637730d40d7",
    "episode:SZ300125:capital_structure_adjustment_path:2025-04-25:"
    "1beca9104a7d",
)
DEFAULT_EPISODE_INDEX = (
    DATA_ROOT / "shared_data/v7/episode_index_v0/episode_index.jsonl"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProbeProvider(Protocol):
    def fetch_daily_basic(self, *, trade_date: str) -> list[dict[str, Any]]: ...

    def fetch_daily_basic_range(
        self, *, symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]: ...


class CrossSectionProbe(StrictModel):
    trade_date: str
    membership_count: int = Field(ge=0)
    provider_row_count: int = Field(ge=0)
    matched_member_count: int = Field(ge=0)
    valid_total_share_count: int = Field(ge=0)
    valid_total_market_value_count: int = Field(ge=0)
    total_share_coverage: float = Field(ge=0, le=1)
    total_market_value_coverage: float = Field(ge=0, le=1)
    matched_total_share_completeness: float = Field(ge=0, le=1)
    matched_total_market_value_completeness: float = Field(ge=0, le=1)
    missing_member_symbols: list[str]
    status: Literal[
        "ready",
        "below_coverage_gate",
        "membership_unavailable",
        "provider_error",
    ]
    error: str = ""


class ShareChangeObservation(StrictModel):
    trade_date: str
    previous_trade_date: str
    previous_total_share: float = Field(ge=0)
    total_share: float = Field(ge=0)
    change_ratio: float | None = None
    nearest_anchor_date: str = ""
    nearest_anchor_calendar_days: int | None = Field(default=None, ge=0)


class CapitalHistoryProbe(StrictModel):
    episode_id: str
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    stock_name: str
    query_start: str
    query_end: str
    anchor_dates: list[str]
    provider_row_count: int = Field(ge=0)
    valid_total_share_rows: int = Field(ge=0)
    share_changes: list[ShareChangeObservation]
    status: Literal[
        "share_history_available",
        "share_history_available_no_change",
        "share_history_unavailable",
        "provider_error",
    ]
    error: str = ""


class ProbeDecision(StrictModel):
    decision_id: str
    status: Literal["accepted_safe_default", "ready", "blocked"]
    recommendation: str
    evidence: str


class P6BProviderProbe(StrictModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    probe_id: str = Field(pattern=r"^P6BP-[A-F0-9]{20}$")
    source_dry_plan_id: Literal[SOURCE_DRY_PLAN_ID] = SOURCE_DRY_PLAN_ID
    generated_at: str
    provider_source: Literal["tushare:daily_basic"] = "tushare:daily_basic"
    cross_sections: list[CrossSectionProbe]
    capital_history: list[CapitalHistoryProbe]
    exact_ready_date_count: int = Field(ge=0)
    provider_history_available_from: str
    single_publishable_history_boundary: str
    recommended_backfill_start: str
    overall_status: Literal[
        "ready_for_scoped_backfill",
        "partial",
        "blocked",
    ]
    decisions: list[ProbeDecision]
    warnings: list[str]


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _iso_date(value: Any, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD: {value!r}") from exc


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 8) if denominator else 0.0


def _load_memberships(
    database: Path, probe_dates: tuple[str, ...]
) -> dict[str, list[str]]:
    placeholders = ",".join("?" for _ in probe_dates)
    with _connect_read_only(database) as connection:
        rows = connection.execute(
            "select trade_date,symbol from st_membership_daily "
            f"where trade_date in ({placeholders}) order by trade_date,symbol",
            probe_dates,
        ).fetchall()
    result = {day: [] for day in probe_dates}
    for row in rows:
        result[str(row["trade_date"])[:10]].append(str(row["symbol"]))
    return result


def _normalize_provider_date(value: Any) -> str:
    raw = str(value or "")
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return _iso_date(raw, field="provider trade_date")


def _cross_section_probe(
    provider: ProbeProvider,
    *,
    trade_date: str,
    membership: list[str],
) -> CrossSectionProbe:
    if not membership:
        return CrossSectionProbe(
            trade_date=trade_date,
            membership_count=0,
            provider_row_count=0,
            matched_member_count=0,
            valid_total_share_count=0,
            valid_total_market_value_count=0,
            total_share_coverage=0,
            total_market_value_coverage=0,
            matched_total_share_completeness=0,
            matched_total_market_value_completeness=0,
            missing_member_symbols=[],
            status="membership_unavailable",
        )
    try:
        rows = provider.fetch_daily_basic(trade_date=trade_date)
        points = normalize_market_cap_rows(
            rows=rows,
            trade_date=trade_date,
            membership_symbols=membership,
        )
    except Exception as exc:  # provider failures belong in the audit result
        return CrossSectionProbe(
            trade_date=trade_date,
            membership_count=len(membership),
            provider_row_count=0,
            matched_member_count=0,
            valid_total_share_count=0,
            valid_total_market_value_count=0,
            total_share_coverage=0,
            total_market_value_coverage=0,
            matched_total_share_completeness=0,
            matched_total_market_value_completeness=0,
            missing_member_symbols=membership,
            status="provider_error",
            error=f"{type(exc).__name__}: {exc}",
        )
    point_symbols = {point.symbol for point in points}
    valid_shares = sum(point.total_shares is not None for point in points)
    valid_market_values = sum(
        point.total_market_value is not None for point in points
    )
    market_value_coverage = _ratio(valid_market_values, len(membership))
    status = (
        "ready"
        if market_value_coverage >= MARKET_CAP_COVERAGE_GATE
        else "below_coverage_gate"
    )
    return CrossSectionProbe(
        trade_date=trade_date,
        membership_count=len(membership),
        provider_row_count=len(rows),
        matched_member_count=len(points),
        valid_total_share_count=valid_shares,
        valid_total_market_value_count=valid_market_values,
        total_share_coverage=_ratio(valid_shares, len(membership)),
        total_market_value_coverage=market_value_coverage,
        matched_total_share_completeness=_ratio(valid_shares, len(points)),
        matched_total_market_value_completeness=_ratio(
            valid_market_values, len(points)
        ),
        missing_member_symbols=sorted(set(membership) - point_symbols),
        status=status,
    )


def _load_capital_records(
    path: Path,
    *,
    episode_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    wanted = set(episode_ids)
    found: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"M6 JSONL 非法: {path}:{line_number}: {exc}") from exc
        episode_id = str(record.get("episode_id") or "")
        if episode_id in wanted:
            if episode_id in found:
                raise ValueError(f"M6 episode_id 重复: {episode_id}")
            found[episode_id] = record
    missing = sorted(wanted - set(found))
    if missing:
        raise ValueError(f"M6 缺冻结 capital probe episode: {missing}")
    return [found[episode_id] for episode_id in episode_ids]


def _share_change_observations(
    rows: list[dict[str, Any]], anchor_dates: list[str]
) -> tuple[int, list[ShareChangeObservation]]:
    normalized: dict[str, float] = {}
    for row in rows:
        value = row.get("total_share")
        if value in (None, ""):
            continue
        day = _normalize_provider_date(row.get("trade_date"))
        number = float(value)
        if number < 0:
            raise ValueError("daily_basic total_share 不得为负")
        previous = normalized.get(day)
        if previous is not None and previous != number:
            raise ValueError(f"daily_basic 同日 total_share 冲突: {day}")
        normalized[day] = number
    changes: list[ShareChangeObservation] = []
    ordered = sorted(normalized.items())
    for (previous_day, previous), (day, current) in zip(
        ordered, ordered[1:], strict=False
    ):
        if current == previous:
            continue
        nearest = min(
            anchor_dates,
            key=lambda anchor: abs(
                (date.fromisoformat(day) - date.fromisoformat(anchor)).days
            ),
            default="",
        )
        distance = (
            abs((date.fromisoformat(day) - date.fromisoformat(nearest)).days)
            if nearest
            else None
        )
        ratio = round(current / previous - 1, 8) if previous else None
        changes.append(ShareChangeObservation(
            trade_date=day,
            previous_trade_date=previous_day,
            previous_total_share=previous,
            total_share=current,
            change_ratio=ratio,
            nearest_anchor_date=nearest,
            nearest_anchor_calendar_days=distance,
        ))
    return len(normalized), changes


def _capital_history_probe(
    provider: ProbeProvider,
    record: dict[str, Any],
    *,
    as_of: str,
) -> CapitalHistoryProbe:
    window = record.get("window") or {}
    query_start = _iso_date(window.get("start_date"), field="window.start_date")
    raw_end = window.get("end_date") or as_of
    query_end = min(_iso_date(raw_end, field="window.end_date"), as_of)
    symbol = str(record.get("symbol") or "")
    anchors = sorted({
        _iso_date(item.get("anchor_date"), field="anchor_date")
        for item in (record.get("anchor_events") or [])
        if item.get("anchor_date") and str(item.get("anchor_date"))[:10] <= as_of
    })
    base = {
        "episode_id": str(record.get("episode_id") or ""),
        "symbol": symbol,
        "stock_name": str(record.get("stock_name") or ""),
        "query_start": query_start,
        "query_end": query_end,
        "anchor_dates": anchors,
    }
    try:
        rows = provider.fetch_daily_basic_range(
            symbol=symbol,
            start_date=query_start,
            end_date=query_end,
        )
        valid_rows, changes = _share_change_observations(rows, anchors)
    except Exception as exc:  # provider failures belong in the audit result
        return CapitalHistoryProbe(
            **base,
            provider_row_count=0,
            valid_total_share_rows=0,
            share_changes=[],
            status="provider_error",
            error=f"{type(exc).__name__}: {exc}",
        )
    if not valid_rows:
        status = "share_history_unavailable"
    elif changes:
        status = "share_history_available"
    else:
        status = "share_history_available_no_change"
    return CapitalHistoryProbe(
        **base,
        provider_row_count=len(rows),
        valid_total_share_rows=valid_rows,
        share_changes=changes,
        status=status,
    )


def _provider_history_start(
    cross_sections: list[CrossSectionProbe],
) -> str:
    if not cross_sections or not all(
        result.provider_row_count > 0
        and result.matched_member_count > 0
        and result.matched_total_share_completeness == 1
        and result.matched_total_market_value_completeness == 1
        for result in cross_sections
    ):
        return ""
    return cross_sections[0].trade_date


def _single_publishable_boundary(
    cross_sections: list[CrossSectionProbe],
) -> str:
    if cross_sections and all(result.status == "ready" for result in cross_sections):
        return cross_sections[0].trade_date
    return ""


def _identifier(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "P6BP-" + hashlib.sha256(canonical.encode()).hexdigest()[:20].upper()


def build_provider_probe(
    *,
    provider: ProbeProvider,
    market_context_database: Path,
    episode_index: Path,
    probe_dates: tuple[str, ...] = FROZEN_PROBE_DATES,
    capital_episode_ids: tuple[str, ...] = CAPITAL_PROBE_EPISODE_IDS,
    as_of: str = "2026-07-20",
) -> P6BProviderProbe:
    effective_as_of = _iso_date(as_of, field="as_of")
    normalized_dates = tuple(
        _iso_date(day, field="probe_date") for day in probe_dates
    )
    if tuple(sorted(set(normalized_dates))) != normalized_dates:
        raise ValueError("probe_dates 必须严格升序且不重复")
    memberships = _load_memberships(
        market_context_database, normalized_dates
    )
    cross_sections = [
        _cross_section_probe(
            provider,
            trade_date=day,
            membership=memberships[day],
        )
        for day in normalized_dates
    ]
    capital_records = _load_capital_records(
        episode_index, episode_ids=capital_episode_ids
    )
    capital_history = [
        _capital_history_probe(provider, record, as_of=effective_as_of)
        for record in capital_records
    ]
    exact_ready = sum(item.status == "ready" for item in cross_sections)
    returned_dates = sum(
        item.provider_row_count > 0 for item in cross_sections
    )
    complete_field_dates = sum(
        item.matched_member_count > 0
        and item.matched_total_share_completeness == 1
        and item.matched_total_market_value_completeness == 1
        for item in cross_sections
    )
    provider_start = _provider_history_start(cross_sections)
    single_boundary = _single_publishable_boundary(cross_sections)
    cross_section_source_ready = all(
        item.provider_row_count > 0
        and item.matched_member_count > 0
        and item.matched_total_share_completeness == 1
        and item.matched_total_market_value_completeness == 1
        for item in cross_sections
    )
    capital_source_ready = all(
        item.status in {
            "share_history_available",
            "share_history_available_no_change",
        }
        for item in capital_history
    )
    if cross_section_source_ready and capital_source_ready:
        overall_status = "ready_for_scoped_backfill"
    elif exact_ready or any(item.valid_total_share_rows for item in capital_history):
        overall_status = "partial"
    else:
        overall_status = "blocked"
    decisions = [
        ProbeDecision(
            decision_id="provider_history_availability",
            status="ready" if provider_start else "blocked",
            recommendation=(
                f"历史 daily_basic 字段可从 {provider_start} 开始做 scoped backfill。"
                if provider_start
                else "冻结样本未证明历史 daily_basic 字段可用；不得启动回填。"
            ),
            evidence=(
                f"{returned_dates}/{len(cross_sections)} 个冻结日期有整市场返回；"
                f"{complete_field_dates}/{len(cross_sections)} 个日期的匹配成员"
                " total_share/total_mv 字段完整。"
            ),
        ),
        ProbeDecision(
            decision_id="publishable_history_boundary",
            status="ready" if single_boundary else "accepted_safe_default",
            recommendation=(
                f"可发布历史边界可冻结为 {single_boundary}。"
                if single_boundary
                else "不声称存在单一连续发布边界；每个锚点日独立执行 95% 覆盖门，"
                "失败日期返回 unavailable。"
            ),
            evidence=(
                f"只有 {exact_ready}/{len(cross_sections)} 个冻结截面通过 "
                f"{MARKET_CAP_COVERAGE_GATE:.0%} 门，且失败在年份间不单调。"
            ),
        ),
        ProbeDecision(
            decision_id="stale_market_cap_policy",
            status="accepted_safe_default",
            recommendation=(
                "P6B-1 默认不使用陈旧市值补足覆盖；目标停牌显示最后有效位置，"
                "cohort 缺值进入 coverage gap。"
            ),
            evidence=(
                "daily_basic 只能观察交易日股本，不能单独证明停牌期间没有"
                " point-in-time 已知的资本结构变化。"
            ),
        ),
        ProbeDecision(
            decision_id="old_shareholder_equity_guard",
            status="blocked",
            recommendation=(
                "历史 total_share 只用于检测股本跳变；老股东稀释与受让权益继续"
                "留在 P6B-2 pilot，不由 P6B-1 推断。"
            ),
            evidence=(
                f"{sum(item.valid_total_share_rows > 0 for item in capital_history)}/"
                f"{len(capital_history)} 个资本结构样本有历史 total_share；"
                "M6 仍无精确 adjuster。"
            ),
        ),
    ]
    warnings = [
        "冻结日期是 source feasibility 样本，不替代逐日 95% 生产覆盖门。",
        "M6 capital episode 与 anchor 仍为 case_note_only；股本跳变只作 provider 能力证据。",
        "provider probe 不写 market_factors、membership 或任何 canonical 数据。",
    ]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "source_dry_plan_id": SOURCE_DRY_PLAN_ID,
        "provider_source": "tushare:daily_basic",
        "cross_sections": [
            item.model_dump(mode="json") for item in cross_sections
        ],
        "capital_history": [
            item.model_dump(mode="json") for item in capital_history
        ],
        "exact_ready_date_count": exact_ready,
        "provider_history_available_from": provider_start,
        "single_publishable_history_boundary": single_boundary,
        "recommended_backfill_start": provider_start,
        "overall_status": overall_status,
        "decisions": [item.model_dump(mode="json") for item in decisions],
        "warnings": warnings,
    }
    return P6BProviderProbe(
        probe_id=_identifier(payload),
        generated_at=datetime.now(timezone.utc).isoformat(),
        **payload,
    )


def render_provider_probe_markdown(probe: P6BProviderProbe) -> str:
    cross_section_rows = "\n".join(
        f"| {item.trade_date} | {item.membership_count} | "
        f"{item.valid_total_market_value_count} | "
        f"{item.total_market_value_coverage:.1%} | {item.status} |"
        for item in probe.cross_sections
    )
    capital_rows = "\n".join(
        f"| {item.symbol} | {item.anchor_dates[0] if item.anchor_dates else '-'} | "
        f"{item.valid_total_share_rows} | {len(item.share_changes)} | {item.status} |"
        for item in probe.capital_history
    )
    decisions = "\n".join(
        f"{index}. **{item.decision_id} / {item.status}**："
        f"{item.recommendation} 证据：{item.evidence}"
        for index, item in enumerate(probe.decisions, 1)
    )
    warnings = "\n".join(f"- {item}" for item in probe.warnings)
    return f"""# P6B provider probe

Probe：`{probe.probe_id}`

来源 dry plan：`{probe.source_dry_plan_id}`

状态：`{probe.overall_status}`

provider 历史可用起点：`{probe.provider_history_available_from or "unavailable"}`

单一连续发布边界：`{probe.single_publishable_history_boundary or "不成立；逐日过门"}`

建议 scoped backfill 起点：`{probe.recommended_backfill_start or "unavailable"}`

## 11 个冻结截面

| 日期 | ST membership | 有效总市值 | 覆盖率 | 状态 |
| --- | ---: | ---: | ---: | --- |
{cross_section_rows}

## 资本结构样本

| 股票 | 首个 anchor | 有效股本日 | 检出跳变 | 状态 |
| --- | --- | ---: | ---: | --- |
{capital_rows}

## 自动采用的安全决定

{decisions}

## 警告

{warnings}
"""


def _load_provider_env(path: Path | None) -> None:
    if path is None:
        return
    if not path.is_file():
        raise FileNotFoundError(path)
    allowed = {"TUSHARE_TOKEN", "TUSHARE_HTTP_URL"}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in allowed:
            os.environ.setdefault(key, value.strip().strip("'\""))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="运行 P6B 冻结日期的只读 Tushare provider probe"
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--market-context-database", type=Path, default=MARKET_CONTEXT_DB
    )
    parser.add_argument(
        "--episode-index", type=Path, default=DEFAULT_EPISODE_INDEX
    )
    parser.add_argument("--as-of", default="2026-07-20")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args(argv)
    _load_provider_env(args.env_file)
    probe = build_provider_probe(
        provider=TushareHttpClient(),
        market_context_database=args.market_context_database,
        episode_index=args.episode_index,
        as_of=args.as_of,
    )
    markdown = render_provider_probe_markdown(probe)
    if args.output_json:
        _write(
            args.output_json,
            json.dumps(
                probe.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    if args.output_markdown:
        _write(args.output_markdown, markdown)
    if not args.output_json and not args.output_markdown:
        print(markdown)
    else:
        print(json.dumps({
            "probe_id": probe.probe_id,
            "overall_status": probe.overall_status,
            "provider_history_available_from": (
                probe.provider_history_available_from
            ),
            "single_publishable_history_boundary": (
                probe.single_publishable_history_boundary
            ),
            "recommended_backfill_start": probe.recommended_backfill_start,
            "output_json": str(args.output_json or ""),
            "output_markdown": str(args.output_markdown or ""),
        }, ensure_ascii=False))
    return 0 if probe.overall_status == "ready_for_scoped_backfill" else 2


if __name__ == "__main__":
    raise SystemExit(main())
