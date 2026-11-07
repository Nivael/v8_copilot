"""Explicit calendar-month windows and price summaries; no inferred risk score."""
from calendar import monthrange
from datetime import date
import math

from market_calendar import sessions_2026


def months_before(value: date, months: int) -> date:
    if months < 1:
        raise ValueError("positive month count required")
    year, month = divmod(value.year * 12 + value.month - 1 - months, 12)
    month += 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def recent_calendar_window(through: str | None) -> dict:
    if not through:
        return {"availability": "unavailable", "reason": "没有已核对的窗口终点"}
    try:
        end = date.fromisoformat(through)
        requested = months_before(end, 2)
        calendar = sessions_2026(date(requested.year, 1, 1), end)
        if calendar[-1] != through:
            raise ValueError("end is not a verified session")
        # Use the last close on/before the requested start; never jump to a later close.
        start = max(day for day in calendar if day <= requested.isoformat())
        days = [day for day in calendar if start <= day <= through]
        return {"availability": "defined", "definition_version": "two_calendar_months_v1",
                "calendar_months": 2, "requested_start": requested.isoformat(),
                "start": start, "end": through, "sessions": len(days) - 1,
                "points": len(days), "calendar": days}
    except (ValueError, IndexError):
        return {"availability": "unavailable", "reason": "两个月窗口超出已核对日历或端点不可用"}


def price_period_summary(closes: list[float | None]) -> dict:
    empty = {"return_pct": None, "max_drawdown_pct": None, "from_peak_pct": None}
    if len(closes) < 2 or any(value is None or isinstance(value, bool) or not math.isfinite(value) or value <= 0 for value in closes):
        return empty
    peak = closes[0]
    drawdowns = []
    for value in closes:
        peak = max(peak, value)
        drawdowns.append((value / peak - 1) * 100)
    return {"return_pct": round((closes[-1] / closes[0] - 1) * 100, 6),
            "max_drawdown_pct": round(min(drawdowns), 6), "from_peak_pct": round(drawdowns[-1], 6)}
