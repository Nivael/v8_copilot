"""All observed weak spells, without fitting a timing or execution rule."""
from decimal import Decimal as D
from st_breadth_alignment import analyze


def compare(evidence):
    inputs = evidence['inputs']
    st = {'daily': inputs['daily'], 'themes': {'current_extension': {'days': inputs['extension_days']}}}
    breadth = {'sequence': {'days': inputs['breadth_days']}}
    replay = analyze(st, breadth)
    if replay != evidence['reading']:
        raise ValueError('alignment evidence failed replay')
    daily = inputs['daily'] + inputs['extension_days']
    bydate = {r['date']: r for r in daily}
    days = [r for r in inputs['breadth_days'] if r['date'] <= replay['common_through']]
    dates = [r['date'] for r in days]
    all_dates = [r['date'] for r in daily]

    def move(ds, key):
        if not ds:
            return None
        value = D(1)
        for day in ds:
            value *= 1 + D(str(bydate[day][key])) / 100
        return float((value - 1) * 100)

    episodes = []
    i = 0
    while i < len(days):
        if days[i]['advancing'] * 2 >= days[i]['trading']:
            i += 1
            continue
        first = i
        while i < len(days) and days[i]['advancing'] * 2 < days[i]['trading']:
            i += 1
        weak_dates = dates[first:i]
        anchor_index = all_dates.index(weak_dates[0]) - 1
        if anchor_index < 0:
            raise ValueError('preceding close missing')
        rows = []
        for wait in (1, 2, 3):
            if len(weak_dates) < wait:
                rows.append({'wait': wait, 'formed': False})
                continue
            at = first + wait - 1
            after = dates[at + 1:at + 6]
            rows.append({'wait': wait, 'formed': True, 'date': dates[at],
                         'already_st_pct': move(dates[first:at+1], 'return_pct'),
                         'already_market_pct': move(dates[first:at+1], 'market_pct'),
                         'following_sessions': len(after),
                         'through': after[-1] if after else dates[at],
                         'partial_st_pct': move(after, 'return_pct'),
                         'partial_market_pct': move(after, 'market_pct'),
                         'five_st_pct': move(after, 'return_pct') if len(after) == 5 else None,
                         'five_market_pct': move(after, 'market_pct') if len(after) == 5 else None})
        episodes.append({'first': weak_dates[0], 'last_observed_weak': weak_dates[-1],
                         'observed_weak_sessions': len(weak_dates),
                         'left_boundary_unknown': first == 0,
                         'ongoing_at_cutoff': i == len(days),
                         'anchor': all_dates[anchor_index], 'checks': rows})
    return {'version': 'breadth_wait_comparison_v1', 'start': dates[0], 'through': dates[-1],
            'observed_sessions': len(days), 'episodes': episodes,
            'independent_validations_added': 0,
            'boundary': '包含仅持续一日或两日的片段及左边界未知片段；一二三日是同段不同观察时刻，不能计为独立案例。随后五日各自起算，可能重叠，不是同一退出终点的策略比较；完整广度收盘后才知道，不假定同价执行。'}
