"""Read-only helpers for recruitment-deadline price-path precedent queries."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


MATERIALIZATION_SCHEMA_VERSION = "v8_recruitment_deadline_materialization_v1"
_DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
)
_CONTEXT_TERMS = (
    "报名材料", "报名期限", "报名截止", "提交材料", "提交报名", "发送至",
    "报名阶段", "报名期间", "报名时间", "申报截止",
)


class RecruitmentMaterializationError(ValueError):
    """The local deadline materialization is absent or malformed."""


@dataclass(frozen=True)
class RecruitmentDeadlineCase:
    announcement_id: str
    symbol: str
    announcement_date: str
    title: str
    recruitment_deadline: str
    source_url: str
    subject_scope: str = "listed_company"
    stock_name: str = ""


def extract_recruitment_deadline(text: str, announcement_date: str) -> str:
    """Extract the best supported application deadline from an announcement body."""
    try:
        announced = date.fromisoformat(announcement_date[:10])
    except ValueError as exc:
        raise RecruitmentMaterializationError(
            f"招募公告日期非法: {announcement_date!r}"
        ) from exc

    normalized = re.sub(r"\s+", "", text)
    candidates: list[tuple[int, int, date]] = []
    for match in _DATE_PATTERN.finditer(normalized):
        try:
            candidate = date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        except ValueError:
            continue
        days_after = (candidate - announced).days
        if days_after < 0 or days_after > 366:
            continue
        before = normalized[max(0, match.start() - 100):match.start()]
        after = normalized[match.end():match.end() + 100]
        context = before + after
        score = sum(4 for term in _CONTEXT_TERMS if term in context)
        score += 3 if any(term in before[-45:] for term in ("应在", "须在", "请于", "自")) else 0
        score += 3 if any(term in after[:45] for term in ("前", "之前", "止", "届满")) else 0
        score += 2 if any(term in after[:80] for term in ("发送", "提交", "报名")) else 0
        score -= 5 if any(term in context for term in ("成立于", "上市", "披露的公告")) else 0
        if score > 0:
            candidates.append((score, match.start(), candidate))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2].isoformat()


def load_recruitment_deadlines(path: Path) -> tuple[list[RecruitmentDeadlineCase], dict[str, Any]]:
    if not path.is_file():
        raise RecruitmentMaterializationError("公开招募截止日尚未独立材料化")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecruitmentMaterializationError("公开招募截止日材料化文件损坏") from exc
    if payload.get("schema_version") != MATERIALIZATION_SCHEMA_VERSION:
        raise RecruitmentMaterializationError("公开招募截止日材料化版本不匹配")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise RecruitmentMaterializationError("公开招募截止日材料化缺 cases")
    cases: list[RecruitmentDeadlineCase] = []
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise RecruitmentMaterializationError(f"公开招募截止日 case[{index}] 非 object")
        try:
            case = RecruitmentDeadlineCase(**{
                field: str(raw.get(field) or "")
                for field in RecruitmentDeadlineCase.__dataclass_fields__
            })
            date.fromisoformat(case.announcement_date)
            date.fromisoformat(case.recruitment_deadline)
        except (TypeError, ValueError) as exc:
            raise RecruitmentMaterializationError(
                f"公开招募截止日 case[{index}] 字段非法"
            ) from exc
        if not all((case.announcement_id, case.symbol, case.title, case.source_url)):
            raise RecruitmentMaterializationError(
                f"公开招募截止日 case[{index}] 缺必需字段"
            )
        cases.append(case)
    return cases, payload


def _consecutive_runs(rows: Iterable[tuple[str, float | None]]) -> list[list[str]]:
    runs: list[list[str]] = []
    current: list[str] = []
    for trade_date, pct_change in rows:
        is_limit_down = pct_change is not None and float(pct_change) <= -4.8
        if is_limit_down:
            current.append(str(trade_date)[:10])
        else:
            if len(current) >= 2:
                runs.append(current)
            current = []
    if len(current) >= 2:
        runs.append(current)
    return runs


def analyze_recruitment_precedents(
    database: Path,
    cases: Iterable[RecruitmentDeadlineCase],
    *,
    price_as_of: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Find consecutive close-limit-down runs inside verified recruitment windows."""
    cases = list(cases)
    covered = 0
    st_eligible = 0
    incomplete_price = 0
    future_deadline = 0
    results: list[dict[str, Any]] = []
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        for case in cases:
            if case.subject_scope != "listed_company":
                continue
            if case.recruitment_deadline > price_as_of:
                future_deadline += 1
                continue
            st_row = connection.execute(
                "select 1 from st_status_history where symbol=? and start_date<=? "
                "and (end_date is null or end_date='' or end_date>=?) "
                "and upper(status_name) like '%ST%' limit 1",
                (case.symbol, case.announcement_date, case.announcement_date),
            ).fetchone()
            if st_row is None:
                continue
            st_eligible += 1
            rows = connection.execute(
                "select trade_date,pct_change from daily_prices "
                "where symbol=? and adjust='qfq' and trade_date>=? and trade_date<=? "
                "order by trade_date",
                (case.symbol, case.announcement_date, case.recruitment_deadline),
            ).fetchall()
            if not rows or str(rows[-1][0])[:10] < case.recruitment_deadline:
                # A weekend/holiday deadline is complete when the price path reaches the
                # last trading day before it. Allow at most four calendar days.
                last_date = date.fromisoformat(str(rows[-1][0])[:10]) if rows else None
                deadline = date.fromisoformat(case.recruitment_deadline)
                if last_date is None or (deadline - last_date).days > 4:
                    incomplete_price += 1
                    continue
            covered += 1
            runs = _consecutive_runs(rows)
            if not runs:
                continue
            longest = max(runs, key=len)
            results.append({
                "announcement_id": case.announcement_id,
                "symbol": case.symbol,
                "stock_name": case.stock_name,
                "announcement_date": case.announcement_date,
                "recruitment_deadline": case.recruitment_deadline,
                "title": case.title,
                "source_url": case.source_url,
                "run_dates": longest,
                "run_length": len(longest),
                "limit_down_days": sum(
                    1 for _, pct_change in rows
                    if pct_change is not None and float(pct_change) <= -4.8
                ),
            })
    results.sort(key=lambda item: (-int(item["run_length"]), item["announcement_date"]))
    return results, {
        "listed_company_cases": sum(1 for case in cases if case.subject_scope == "listed_company"),
        "st_eligible_cases": st_eligible,
        "price_covered_cases": covered,
        "precedent_cases": len(results),
        "incomplete_price_cases": incomplete_price,
        "future_deadline_cases": future_deadline,
    }
