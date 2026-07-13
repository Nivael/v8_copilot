"""Resolve user-facing stock names to canonical symbols from read-only v5 metadata."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from settings import DATA_ROOT


STOCK_META_DB = (
    DATA_ROOT / "shared_data/v5/universe_2026_st/st_stocks_2026_st_working.sqlite3"
)
_SYMBOL_RE = re.compile(r"(?<![0-9])([0-9]{6})(?![0-9])")
_LEADING_STATUS_RE = re.compile(r"^(?:\*?ST|SST|S\*ST|退)+", re.IGNORECASE)
_COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
)


@dataclass(frozen=True)
class StockResolution:
    symbol: str
    display_name: str
    matched_alias: str


def _connect_read_only() -> sqlite3.Connection:
    if not STOCK_META_DB.is_file():
        raise FileNotFoundError(f"股票主数据不存在: {STOCK_META_DB}")
    return sqlite3.connect(f"file:{STOCK_META_DB}?mode=ro", uri=True)


def normalize_stock_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).upper()
    text = re.sub(r"[\s·•._()（）\-—]", "", text)
    text = _LEADING_STATUS_RE.sub("", text)
    for suffix in _COMPANY_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text


@lru_cache(maxsize=1)
def _alias_catalog() -> tuple[tuple[str, str, str], ...]:
    with _connect_read_only() as connection:
        current = connection.execute(
            "select symbol,name from stocks_meta where symbol glob '[0-9][0-9][0-9][0-9][0-9][0-9]'"
        ).fetchall()
        changes = connection.execute(
            "select symbol,old_name,new_name from name_changes"
        ).fetchall()

    display_names = {str(symbol): str(name) for symbol, name in current}
    aliases: set[tuple[str, str, str]] = set()
    for symbol, name in current:
        normalized = normalize_stock_name(str(name))
        if len(normalized) >= 2:
            aliases.add((normalized, str(symbol), str(name)))
    for symbol, old_name, new_name in changes:
        display_name = display_names.get(str(symbol), str(new_name or old_name or symbol))
        for alias in (old_name, new_name):
            if not alias:
                continue
            normalized = normalize_stock_name(str(alias))
            if len(normalized) >= 2:
                aliases.add((normalized, str(symbol), display_name))
    return tuple(sorted(aliases, key=lambda item: (-len(item[0]), item[0], item[1])))


def resolve_stock(value: str) -> StockResolution | None:
    symbol_match = _SYMBOL_RE.search(value)
    if symbol_match:
        symbol = symbol_match.group(1)
        names = {
            candidate_symbol: display_name
            for _, candidate_symbol, display_name in _alias_catalog()
        }
        return StockResolution(symbol, names.get(symbol, symbol), symbol)

    normalized_question = normalize_stock_name(value)
    matches = [
        item for item in _alias_catalog()
        if item[0] and item[0] in normalized_question
    ]
    if not matches:
        return None
    longest = len(matches[0][0])
    strongest = [item for item in matches if len(item[0]) == longest]
    symbols = {item[1] for item in strongest}
    if len(symbols) != 1:
        return None
    alias, symbol, display_name = strongest[0]
    return StockResolution(symbol, display_name, alias)


def resolve_stocks(value: str) -> list[StockResolution]:
    """Resolve every distinct stock mention in stable textual order."""
    names = {
        candidate_symbol: display_name
        for _, candidate_symbol, display_name in _alias_catalog()
    }
    hits: list[tuple[int, int, StockResolution]] = []
    for match in _SYMBOL_RE.finditer(value):
        symbol = match.group(1)
        hits.append((match.start(), -6, StockResolution(symbol, names.get(symbol, symbol), symbol)))

    normalized = normalize_stock_name(value)
    for alias, symbol, display_name in _alias_catalog():
        start = normalized.find(alias)
        if start >= 0:
            hits.append((start, -len(alias), StockResolution(symbol, display_name, alias)))

    resolved: list[StockResolution] = []
    seen: set[str] = set()
    for _, _, item in sorted(hits, key=lambda row: (row[0], row[1], row[2].symbol)):
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        resolved.append(item)
    return resolved
