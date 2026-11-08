"""Optional display annotation, bound to the independently checked snapshot and quote cutoff."""
from math import isfinite


def attach_price_window_notes(view, regime):
    check=regime.get('themes',{}).get('stock_price_crosscheck')
    if regime.get('availability')!='available' or not check:
        return view
    for case in view.get('cases',[]):
        quote=case.get('latest_quote') or {}
        row=next((r for r in check['rows'] if r['symbol']==case['symbol'][:6]),None)
        if not row or quote.get('as_of')!=check['through']:
            continue
        window=row['windows']['20'];reference=window.get('reference_price_change_pct');alternative=window.get('alternative_actual_anchor')
        reported=quote.get('twenty_day_change_pct')
        matches=reported is None or type(reported) in (int,float) and isfinite(reported) and reference is not None and abs(reported-reference)<.02
        if window['stock_pct'] is None and window.get('gap') and alternative and reference is not None and matches:
            prefix=f"近20日未计算：共同起点{window['anchor']}停牌、没有实际成交收盘；按参考价回看的变化为{reference:+.2f}%，不充当成交起点。" if reported is None else f"近20日数值含{window['anchor']}的停牌参考价，不是当日实际成交起点。"
            case['price_window_note']={'source_snapshot':regime['content_digest'],'text':prefix+f"若改从前次实际收盘{alternative['anchor']}观察，跨{alternative['market_days']}个市场交易日、其中{alternative['actual_trading_days']}个个股成交日。两种窗口在横向复盘第一题的五股核对中分别列示。"}
    return view

