"""Replay a reviewed agreement casebook against local prices, without network or writes to SQLite.

This is exploratory research, not a released Lens or a trading/backtest signal.
Run: python benchmarks/agreement_event_study.py --output out/agreement-study.json
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from settings import BASE_DB


def event_window(prices: list[tuple[str, float]], publication: str, *, next_session: bool = False) -> dict:
    """n observed sessions, previous close baseline; never fill a missing endpoint."""
    if any(not value > 0 for _, value in prices):
        raise ValueError('Non-positive or NaN price')
    days = [day for day, _ in prices]
    if days != sorted(set(days)):
        raise ValueError('Prices must have unique ascending dates')
    index = bisect_left(days, publication)
    if next_session and index < len(days) and days[index] == publication:
        index += 1
    if index == 0 or index >= len(prices):
        return {'coverage_gap': 'No baseline or post-event observation'}
    baseline_day, baseline = prices[index - 1]
    result = {'publication': publication, 'baseline_date': baseline_day,
              'baseline_close_qfq': baseline, 'first_session': days[index],
              'source_as_of': days[-1], 'observations_after_event': len(prices) - index}
    # A long source gap is not silently called a verified suspension.
    if (date.fromisoformat(days[index]) - date.fromisoformat(publication)).days > 7:
        result['coverage_gap'] = 'First observation delayed >7 calendar days; suspension/data gap unverified'
        return result
    for horizon in (5, 20, 60):
        if index + horizon > len(prices):
            result[f'return_{horizon}'] = None
            continue
        window = prices[index:index + horizon]
        peak, drawdown = baseline, 0.0
        for _, close in window:
            peak = max(peak, close)
            drawdown = min(drawdown, close / peak - 1)
        result.update({f'return_{horizon}': round(100 * (window[-1][1] / baseline - 1), 3),
                       f'end_{horizon}': window[-1][0],
                       f'max_drawdown_{horizon}': round(100 * drawdown, 3)})
    return result


def summarize(cases: list[dict]) -> dict:
    later = [case for case in cases if case['financial_disclosure'] > case['industrial_disclosure']]
    summary = {'paired_cases': len(cases), 'later_financial_cases': len(later),
               'later_price_higher': sum(c['financial_price'] > c['industrial_price'] for c in later),
               'later_price_lower': sum(c['financial_price'] < c['industrial_price'] for c in later)}
    for horizon in (5, 20, 60):
        values = [c['price_window'].get(f'return_{horizon}') for c in later]
        observed = [v for v in values if v is not None]
        summary[str(horizon)] = {'n': len(observed), 'missing': len(values) - len(observed),
                                'positive': sum(v > 0 for v in observed),
                                'negative': sum(v < 0 for v in observed),
                                'flat': sum(v == 0 for v in observed),
                                'median': statistics.median(observed) if len(observed) >= 8 else None}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--casebook', type=Path, default=Path(__file__).parent / 'fixtures/investor_agreements_20260910.json')
    parser.add_argument('--db', type=Path, default=BASE_DB)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    raw = args.casebook.read_bytes()
    casebook = json.loads(raw)
    symbols = sorted({case['symbol'] for case in casebook['cases']})
    read_start = time.perf_counter()
    with sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        series = {symbol: connection.execute(
            'select trade_date, close from daily_prices where symbol=? and adjust=? order by trade_date',
            (symbol, 'qfq')).fetchall() for symbol in symbols}
    read_seconds = time.perf_counter() - read_start
    cases = [{**case, 'price_window': event_window(series[case['symbol']], case['financial_disclosure']),
              'next_session_window': event_window(series[case['symbol']], case['financial_disclosure'], next_session=True)}
             for case in casebook['cases']]
    payload = {'scope': casebook['scope'], 'not_released_lens': True, 'not_causal': True,
               'casebook_sha256': hashlib.sha256(raw).hexdigest(),
               'price_rows_sha256': hashlib.sha256(json.dumps(series, sort_keys=True).encode()).hexdigest(),
               'casebook': casebook, 'cases': cases, 'summary': summarize(cases),
               'next_session_sensitivity': summarize([{**c, 'price_window': c['next_session_window']} for c in cases]),
               'timing': {'read_seconds': read_seconds, 'total_seconds_before_write': time.perf_counter() - started}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'summary': payload['summary'], 'timing': payload['timing']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
