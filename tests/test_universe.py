from __future__ import annotations

import json

from universe import (
    StUniverseRepository,
    StUniverseService,
    build_st_universe_snapshot,
)


def _rows(day: str, symbols: list[str]) -> list[dict]:
    return [{
        "ts_code": f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ",
        "name": f"ST {symbol}",
        "trade_date": day.replace("-", ""),
        "type": "S",
        "type_name": "ST",
    } for symbol in symbols]


def test_snapshot_is_sorted_deterministic_and_repository_is_idempotent(tmp_path) -> None:
    first = build_st_universe_snapshot(
        as_of="2026-07-20",
        rows=_rows("2026-07-20", ["603398", "000408"]),
        fetched_at="2026-07-20T10:00:00+00:00",
    )
    second = build_st_universe_snapshot(
        as_of="2026-07-20",
        rows=_rows("2026-07-20", ["000408", "603398"]),
        fetched_at="2026-07-20T11:00:00+00:00",
    )
    repository = StUniverseRepository(tmp_path / "universe")

    first_path = repository.write(first)
    second_path = repository.write(second)

    assert first.content_digest == second.content_digest
    assert first_path == second_path
    assert repository.load_current().symbols == ["000408", "603398"]
    assert len(list((tmp_path / "universe" / "snapshots").glob("*.json"))) == 1


def test_removed_member_is_not_mislabelled_as_delisted() -> None:
    previous = build_st_universe_snapshot(
        as_of="2026-07-18", rows=_rows("2026-07-18", ["000408", "603398"])
    )
    current = build_st_universe_snapshot(
        as_of="2026-07-20", rows=_rows("2026-07-20", ["000408"]), previous=previous
    )

    assert current.removed_symbols == ["603398"]
    assert "退市" in current.notes[0]
    assert "delisted" not in json.dumps(current.model_dump(), ensure_ascii=False).lower()


class FakeProvider:
    def fetch_st_universe(self, *, as_of: str) -> list[dict]:
        return _rows(as_of, ["000408", "603398"])


def test_service_materializes_authoritative_provider_response(tmp_path) -> None:
    repository = StUniverseRepository(tmp_path / "universe")
    snapshot, path = StUniverseService(
        provider=FakeProvider(), repository=repository
    ).sync(as_of="2026-07-20")

    assert snapshot.member_count == 2
    assert snapshot.added_symbols == ["000408", "603398"]
    assert path.is_file()


def test_snapshot_rejects_response_from_a_different_day() -> None:
    try:
        build_st_universe_snapshot(
            as_of="2026-07-20", rows=_rows("2026-07-18", ["000408"])
        )
    except ValueError as exc:
        assert "不一致" in str(exc)
    else:
        raise AssertionError("different-day response must fail closed")


def test_snapshot_rejects_empty_provider_response() -> None:
    try:
        build_st_universe_snapshot(as_of="2026-07-20", rows=[])
    except ValueError as exc:
        assert "空名单" in str(exc)
    else:
        raise AssertionError("empty universe must fail closed")
