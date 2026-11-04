"""Versioned exchange sessions; unsupported years fail instead of guessing holidays."""
from datetime import date, timedelta

CALENDAR_VERSION = "sse_announced_sessions_2026_v1"
CALENDAR_SOURCE = "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml"
HOLIDAY_RANGES_2026 = (
    ("2026-01-01", "2026-01-03"), ("2026-02-15", "2026-02-23"),
    ("2026-04-04", "2026-04-06"), ("2026-05-01", "2026-05-05"),
    ("2026-06-19", "2026-06-21"), ("2026-09-25", "2026-09-27"),
    ("2026-10-01", "2026-10-07"),
)


def sessions_2026(start: date, end: date) -> list[str]:
    if start.year != 2026 or end.year != 2026 or start > end:
        raise ValueError("Only the verified 2026 exchange calendar is supported")
    result = []
    day = start
    while day <= end:
        text = day.isoformat()
        if day.weekday() < 5 and not any(first <= text <= last for first, last in HOLIDAY_RANGES_2026):
            result.append(text)
        day += timedelta(days=1)
    return result
