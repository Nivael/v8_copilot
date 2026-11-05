"""Calendar distance is separate from snapshot validity and provider publication SLAs."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from canonical_json import digest
from market_calendar import CALENDAR_SOURCE, CALENDAR_VERSION, HOLIDAY_RANGES_2026, sessions_2026

VERSION = 'market_close_distance_v1'
HOURS_SOURCE = 'https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml'
RULE_EFFECTIVE = date(2026, 7, 6)


def close_reference(now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError('observation time must be timezone-aware')
    local = now.astimezone(ZoneInfo('Asia/Shanghai'))
    base = {'version': VERSION, 'availability': 'unavailable', 'observed_at': now.isoformat(),
            'timezone': 'Asia/Shanghai', 'reference_time': '15:00', 'latest_scheduled_close': None,
            'calendar_version': CALENDAR_VERSION, 'calendar_source': CALENDAR_SOURCE,
            'hours_source': HOURS_SOURCE, 'schedule_only': True,
            'provider_deadline_verified': False, 'automatic_update_observed': False}
    # This clock rule is checked against the currently reviewed rule version only.
    if local.year != 2026 or local.date() < RULE_EFFECTIVE:
        return {**base, 'reason': 'outside_reviewed_calendar_or_hours_version'}
    days = sessions_2026(date(2026, 1, 1), local.date())
    completed = [day for day in days if day < local.date().isoformat() or local.time() >= time(15)]
    if not completed or completed[-1] < RULE_EFFECTIVE.isoformat():
        return {**base, 'reason': 'no_reviewed_scheduled_close'}
    return {**base, 'availability': 'calendar_computed', 'latest_scheduled_close': completed[-1],
            'calendar_rule_digest': digest({'version': CALENDAR_VERSION, 'holidays': HOLIDAY_RANGES_2026,
                                           'hours_source': HOURS_SOURCE, 'reviewed_from': RULE_EFFECTIVE.isoformat(),
                                           'timezone': 'Asia/Shanghai', 'reference_time': '15:00'})}


def close_distance(through_dates: list[str], reference: dict) -> dict:
    base = {'availability': 'unavailable', 'minimum_sessions': None, 'maximum_sessions': None,
            'series_compared': 0, 'latest_scheduled_close': reference.get('latest_scheduled_close')}
    if reference.get('availability') != 'calendar_computed':
        return {**base, 'reason': 'reference_unavailable'}
    if not through_dates:
        return {**base, 'reason': 'no_verified_data_dates'}
    try:
        end = date.fromisoformat(reference['latest_scheduled_close'])
        days = sessions_2026(date(2026, 1, 1), date(2026, 12, 31))
        values = []
        for value in through_dates:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value or parsed.year != 2026:
                raise ValueError('unsupported data date')
            if value not in days:
                return {**base, 'reason': 'data_date_not_a_session'}
            if parsed > end:
                return {**base, 'reason': 'data_after_reference'}
            values.append(sum(value < day <= end.isoformat() for day in days))
        return {**base, 'availability': 'compared', 'minimum_sessions': min(values),
                'maximum_sessions': max(values), 'series_compared': len(values)}
    except (ValueError, TypeError, KeyError):
        return {**base, 'reason': 'invalid_or_unsupported_data_date'}
