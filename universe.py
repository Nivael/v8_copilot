"""Authoritative, append-only ST universe snapshots.

The universe is a maintenance input, not a property inferred from whatever rows
happen to exist in the research database.  The answer path may read a promoted
snapshot, but only the dedicated maintenance command writes snapshots.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from data_refresh import atomic_write_json


ST_UNIVERSE_CONTRACT_VERSION = "v8_st_universe_v1"
ST_UNIVERSE_SOURCE_ID = "tushare_stock_st"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StUniverseMember(StrictModel):
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    ts_code: str
    name: str
    membership_date: str
    risk_type: str = ""
    risk_type_name: str = ""
    source_id: Literal[ST_UNIVERSE_SOURCE_ID] = ST_UNIVERSE_SOURCE_ID


class StUniverseSnapshot(StrictModel):
    contract_version: Literal[ST_UNIVERSE_CONTRACT_VERSION] = ST_UNIVERSE_CONTRACT_VERSION
    snapshot_id: str = Field(pattern=r"^SU-[A-F0-9]{20}$")
    as_of: str
    fetched_at: str
    source_id: Literal[ST_UNIVERSE_SOURCE_ID] = ST_UNIVERSE_SOURCE_ID
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    member_count: int = Field(ge=0)
    members: list[StUniverseMember]
    added_symbols: list[str] = Field(default_factory=list)
    removed_symbols: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def symbols(self) -> list[str]:
        return [member.symbol for member in self.members]


class StUniverseProvider(Protocol):
    def fetch_st_universe(self, *, as_of: str) -> list[dict[str, Any]]: ...


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"as_of 必须是 YYYY-MM-DD: {value!r}") from exc


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(as_of: str, members: list[StUniverseMember]) -> str:
    payload = {
        "as_of": as_of,
        "source_id": ST_UNIVERSE_SOURCE_ID,
        "members": [member.model_dump(mode="json") for member in members],
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def build_st_universe_snapshot(
    *,
    as_of: str,
    rows: list[dict[str, Any]],
    previous: StUniverseSnapshot | None = None,
    fetched_at: str | None = None,
) -> StUniverseSnapshot:
    """Normalize one authoritative daily membership response.

    A symbol disappearing from the next snapshot is recorded as ``removed``.
    It is deliberately not labelled "delisted": removal can also mean an ST
    designation was revoked.
    """

    target = _iso_date(as_of)
    if not rows:
        raise ValueError("stock_st 返回空名单；拒绝将其提升为 current universe")
    by_symbol: dict[str, StUniverseMember] = {}
    for raw in rows:
        ts_code = str(raw.get("ts_code") or "").strip().upper()
        symbol = ts_code.split(".", 1)[0]
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"stock_st 返回非法 ts_code: {ts_code!r}")
        raw_date = str(raw.get("trade_date") or target).replace("-", "")
        if len(raw_date) != 8 or not raw_date.isdigit():
            raise ValueError(f"stock_st 返回非法 trade_date: {raw_date!r}")
        membership_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        if membership_date != target:
            raise ValueError(
                f"stock_st 行日期 {membership_date} 与请求日期 {target} 不一致"
            )
        member = StUniverseMember(
            symbol=symbol,
            ts_code=ts_code,
            name=str(raw.get("name") or "").strip(),
            membership_date=membership_date,
            risk_type=str(raw.get("type") or "").strip(),
            risk_type_name=str(raw.get("type_name") or "").strip(),
        )
        if symbol in by_symbol and by_symbol[symbol] != member:
            raise ValueError(f"stock_st 同日同股票出现冲突行: {symbol}")
        by_symbol[symbol] = member
    members = [by_symbol[symbol] for symbol in sorted(by_symbol)]
    digest = _digest(target, members)
    old = set(previous.symbols if previous else [])
    new = set(by_symbol)
    return StUniverseSnapshot(
        snapshot_id=f"SU-{digest[:20].upper()}",
        as_of=target,
        fetched_at=fetched_at or datetime.now(timezone.utc).isoformat(),
        content_digest=digest,
        member_count=len(members),
        members=members,
        added_symbols=sorted(new - old),
        removed_symbols=sorted(old - new),
        notes=[
            "removed_symbols 仅表示不再属于当日 ST 名单；不得据此推断退市。"
        ] if old - new else [],
    )


class StUniverseRepository:
    """Append-only dated snapshots plus an atomic current pointer."""

    def __init__(self, root: Path):
        self.root = root

    @property
    def snapshots_dir(self) -> Path:
        return self.root / "snapshots"

    @property
    def current_path(self) -> Path:
        return self.root / "current.json"

    def load_current(self) -> StUniverseSnapshot | None:
        if not self.current_path.is_file():
            return None
        pointer = json.loads(self.current_path.read_text(encoding="utf-8"))
        relative = str(pointer.get("snapshot_path") or "")
        path = (self.root / relative).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("ST universe current pointer 越出仓库根目录")
        return self.load(path)

    @staticmethod
    def load(path: Path) -> StUniverseSnapshot:
        return StUniverseSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def write(self, snapshot: StUniverseSnapshot) -> Path:
        expected = _digest(snapshot.as_of, snapshot.members)
        if snapshot.content_digest != expected:
            raise ValueError("ST universe content_digest 与内容不一致")
        name = f"{snapshot.as_of}_{snapshot.content_digest[:12]}.json"
        destination = self.snapshots_dir / name
        payload = snapshot.model_dump(mode="json")
        if destination.is_file():
            existing = StUniverseSnapshot.model_validate_json(
                destination.read_text(encoding="utf-8")
            )
            if existing.content_digest != snapshot.content_digest:
                raise ValueError(f"已有同名 universe snapshot 内容冲突: {destination}")
        else:
            atomic_write_json(destination, payload)
        atomic_write_json(self.current_path, {
            "contract_version": ST_UNIVERSE_CONTRACT_VERSION,
            "snapshot_id": snapshot.snapshot_id,
            "as_of": snapshot.as_of,
            "content_digest": snapshot.content_digest,
            "snapshot_path": str(destination.relative_to(self.root)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return destination


class StUniverseService:
    def __init__(self, *, provider: StUniverseProvider, repository: StUniverseRepository):
        self.provider = provider
        self.repository = repository

    def sync(self, *, as_of: str) -> tuple[StUniverseSnapshot, Path]:
        previous = self.repository.load_current()
        rows = self.provider.fetch_st_universe(as_of=_iso_date(as_of))
        snapshot = build_st_universe_snapshot(as_of=as_of, rows=rows, previous=previous)
        return snapshot, self.repository.write(snapshot)
