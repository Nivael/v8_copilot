"""Fail-loudly metadata readers for the local read-only research snapshots."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class SnapshotContractError(ValueError):
    """A local snapshot cannot support a truthful freshness declaration."""


@dataclass(frozen=True)
class TableSnapshot:
    table: str
    min_date: str
    as_of: str
    row_count: int


@dataclass(frozen=True)
class PriceSnapshot(TableSnapshot):
    symbol_count: int
    return_observation_count: int


@dataclass(frozen=True)
class EpisodeSnapshot:
    version: str
    as_of: str
    row_count: int


def _iso_date(value: object, *, field: str) -> str:
    text = str(value)[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError) as exc:
        raise SnapshotContractError(f"{field} 日期非法: {value!r}") from exc


def _connect_read_only(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise SnapshotContractError(f"研究数据库不存在: {database}")
    try:
        return sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise SnapshotContractError(f"研究数据库无法只读打开: {database}: {exc}") from exc


def load_table_snapshot(
    database: Path,
    *,
    table: str,
    date_column: str,
    where_sql: str = "",
    parameters: tuple[object, ...] = (),
    expected_as_of: str | None = None,
) -> TableSnapshot:
    if not table.replace("_", "").isalnum() or not date_column.replace("_", "").isalnum():
        raise SnapshotContractError("table/date_column 只能使用数据库标识符")
    with _connect_read_only(database) as connection:
        columns = {
            str(row[1]) for row in connection.execute(f"pragma table_info({table})").fetchall()
        }
        if not columns:
            raise SnapshotContractError(f"研究数据库缺表: {table}")
        if date_column not in columns:
            raise SnapshotContractError(f"{table} 缺日期字段: {date_column}")
        suffix = f" where {where_sql}" if where_sql else ""
        try:
            row = connection.execute(
                f"select min({date_column}),max({date_column}),count(*) from {table}{suffix}",
                parameters,
            ).fetchone()
        except sqlite3.Error as exc:
            raise SnapshotContractError(f"读取 {table} 快照元数据失败: {exc}") from exc
    if not row or not row[0] or not row[1] or int(row[2]) <= 0:
        raise SnapshotContractError(f"{table} 快照为空，无法声明 freshness")
    snapshot = TableSnapshot(
        table,
        _iso_date(row[0], field=f"{table}.min_date"),
        _iso_date(row[1], field=f"{table}.as_of"),
        int(row[2]),
    )
    if expected_as_of is not None and snapshot.as_of != expected_as_of:
        raise SnapshotContractError(
            f"{table} as_of 不匹配: 声明 {expected_as_of}，实际 {snapshot.as_of}"
        )
    return snapshot


def load_price_snapshot(
    database: Path,
    *,
    expected_as_of: str | None = None,
) -> PriceSnapshot:
    base = load_table_snapshot(
        database,
        table="daily_prices",
        date_column="trade_date",
        where_sql="adjust='qfq'",
        expected_as_of=expected_as_of,
    )
    with _connect_read_only(database) as connection:
        columns = {
            str(row[1]) for row in connection.execute("pragma table_info(daily_prices)").fetchall()
        }
        missing = {"symbol", "close", "adjust"} - columns
        if missing:
            raise SnapshotContractError(
                f"daily_prices 缺必需字段: {', '.join(sorted(missing))}"
            )
        symbol_count = int(connection.execute(
            "select count(distinct symbol) from daily_prices where adjust='qfq'"
        ).fetchone()[0])
        return_count = int(connection.execute(
            "select coalesce(sum(case when n > 10 then n - 10 else 0 end), 0) "
            "from (select count(*) n from daily_prices where adjust='qfq' group by symbol)"
        ).fetchone()[0])
    if symbol_count <= 0 or return_count <= 0:
        raise SnapshotContractError("daily_prices qfq 快照缺少可计算的股票或两周收益观测")
    return PriceSnapshot(
        table=base.table,
        min_date=base.min_date,
        as_of=base.as_of,
        row_count=base.row_count,
        symbol_count=symbol_count,
        return_observation_count=return_count,
    )


def load_episode_snapshot(
    index_path: Path,
    manifest_path: Path,
    *,
    expected_as_of: str | None = None,
) -> EpisodeSnapshot:
    if not manifest_path.is_file():
        raise SnapshotContractError(f"episode manifest 不存在: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotContractError(f"episode manifest 非法: {manifest_path}: {exc}") from exc
    version = manifest.get("builder_version")
    as_of = manifest.get("as_of")
    if not isinstance(version, str) or not version or not isinstance(as_of, str) or not as_of:
        raise SnapshotContractError("episode manifest 缺 builder_version/as_of")
    as_of = _iso_date(as_of, field="episode.as_of")
    if expected_as_of is not None and as_of != expected_as_of:
        raise SnapshotContractError(
            f"episode as_of 不匹配: 声明 {expected_as_of}，实际 {as_of}"
        )
    if not index_path.is_file():
        raise SnapshotContractError(f"episode index 不存在: {index_path}")
    row_count = 0
    try:
        with index_path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SnapshotContractError(
                        f"episode index JSON 非法: {index_path}:{line_number}: {exc}"
                    ) from exc
                if not isinstance(row, dict):
                    raise SnapshotContractError(
                        f"episode index 行必须是 object: {index_path}:{line_number}"
                    )
                row_count += 1
    except OSError as exc:
        raise SnapshotContractError(f"episode index 无法读取: {index_path}: {exc}") from exc
    if row_count == 0:
        raise SnapshotContractError("episode index 为空")
    return EpisodeSnapshot(version=version, as_of=as_of, row_count=row_count)


def limiting_as_of(*values: str) -> str:
    clean = [
        _iso_date(value, field="source_freshness") for value in values if value
    ]
    if not clean:
        raise SnapshotContractError("无法从空数据源计算 as_of")
    return min(clean)
