"""Describe waiting cost to a calendar-fixed endpoint, without an execution model."""
from datetime import date
from decimal import Decimal as D
from breadth_wait_comparison import compare
from market_calendar import sessions_2026


def compare_common_end(source):
    original = compare(source)
    daily = source['inputs']['daily'] + source['inputs']['extension_days']
    bydate = {row['date']: row for row in daily}
    calendar = sessions_2026(date.fromisoformat(original['start']), date(2026, 12, 31))

    def change(days, key):
        value = D(1)
        for day in days:
            value *= 1 + D(str(bydate[day][key])) / 100
        return float((value - 1) * 100) if days else 0.0

    episodes = []
    for episode in original['episodes']:
        start = calendar.index(episode['first'])
        target = calendar[start + 5]
        observed_end = min(target, original['through'])
        total_days = [day for day in calendar[start:start + 6] if day <= observed_end]
        complete = target <= original['through']
        checks = []
        total_st = change(total_days, 'return_pct')
        total_market = change(total_days, 'market_pct')
        for old in episode['checks']:
            if not old['formed']:
                checks.append({'wait': old['wait'], 'formed': False})
                continue
            after = [day for day in total_days if day > old['date']]
            st = change(after, 'return_pct')
            market = change(after, 'market_pct')
            for earlier, later, total in ((old['already_st_pct'], st, total_st),
                                           (old['already_market_pct'], market, total_market)):
                if abs(((1+earlier/100)*(1+later/100)-1)*100-total) > 1e-10:
                    raise ValueError('before/after composition mismatch')
            checks.append({'wait': old['wait'], 'formed': True, 'date': old['date'],
                           'already_st_pct': old['already_st_pct'],
                           'already_market_pct': old['already_market_pct'],
                           'remaining_sessions': len(after),
                           'remaining_st_pct': st if complete else None,
                           'remaining_market_pct': market if complete else None,
                           'partial_st_pct': st, 'partial_market_pct': market})
        episodes.append({k: v for k, v in episode.items() if k != 'checks'} | {
            'target_end': target, 'observed_end': observed_end, 'complete': complete,
            'total_st_pct': total_st if complete else None,
            'total_market_pct': total_market if complete else None, 'checks': checks})
    return {'version': 'breadth_common_end_v1', 'start': original['start'],
            'through': original['through'], 'episodes': episodes,
            'endpoint_rule': '每段首个可观察偏弱日收盘之后第5个交易日；与等待一二三日无关。',
            'boundary': '同一终点只消除了终点差异，各行剩余天数不同。条件未形成的片段仍保留，不把它们当作无风险；首段起点未知。同段不同等待不增加独立案例。没有同价执行、空仓现金、再入场与交易成本模型，不推减仓效果或最优等待天数。',
            'independent_validations_added': 0}
