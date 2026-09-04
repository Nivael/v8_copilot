"""Read-only merge of canonical qfq prices and the scoped P8 history overlay."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path


def _rows(path: Path, start: str, through: str):
    if not path.is_file():
        return []
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        tables = {str(row[0]) for row in connection.execute("select name from sqlite_master where type='table'")}
        if "daily_prices" not in tables:
            return []
        return connection.execute(
            "select symbol,trade_date,close from daily_prices where adjust='qfq' "
            "and trade_date between ? and ? and close>0 order by symbol,trade_date",
            (start, through),
        ).fetchall()


def qfq_close(
    base_database: Path, *, overlay_database: Path | None,
    start: str, through: str,
) -> dict[tuple[str, str], float]:
    result = {(str(symbol), str(day)): float(close) for symbol, day, close in _rows(base_database, start, through)}
    if overlay_database:
        result.update({
            (str(symbol), str(day)): float(close)
            for symbol, day, close in _rows(overlay_database, start, through)
        })
    return result


def qfq_series(
    base_database: Path, *, overlay_database: Path | None,
    start: str, through: str,
) -> dict[str, list[tuple[str, float]]]:
    merged = qfq_close(
        base_database, overlay_database=overlay_database, start=start, through=through,
    )
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (symbol, day), close in sorted(merged.items()):
        result[symbol].append((day, close))
    return dict(result)
