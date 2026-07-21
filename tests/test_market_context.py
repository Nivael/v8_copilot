from __future__ import annotations

from market_context import (
    BROAD_MARKET,
    BenchmarkDefinition,
    MarketContextRepository,
    MarketContextService,
    build_st_equal_weight_points,
)


def test_equal_weight_index_uses_daily_membership_and_exposes_coverage() -> None:
    points = build_st_equal_weight_points(
        membership_by_date={
            "2026-07-17": {"000001", "000002"},
            "2026-07-20": {"000002", "000003"},
        },
        returns_by_date={
            "2026-07-17": {"000001": -2.0, "000002": 0.0},
            "2026-07-20": {"000001": 99.0, "000002": -3.0, "000003": None},
        },
    )

    assert points[0].pct_change == -1.0
    assert points[0].close == 990.0
    assert points[1].pct_change == -3.0
    assert points[1].close == 960.3
    assert points[1].member_count == 2
    assert points[1].valid_member_count == 1
    assert points[1].coverage_ratio == 0.5


def test_equal_weight_index_fails_without_historical_membership() -> None:
    try:
        build_st_equal_weight_points(
            membership_by_date={}, returns_by_date={"2026-07-20": {"000001": 1.0}}
        )
    except ValueError as exc:
        assert "幸存者偏差" in str(exc)
    else:
        raise AssertionError("missing membership must fail closed")


class FakeIndexProvider:
    def fetch_index_daily(self, *, ts_code: str, start_date: str, end_date: str):
        assert ts_code == "000985.CSI"
        return [{
            "ts_code": ts_code,
            "trade_date": "20260720",
            "open": 5000,
            "high": 5010,
            "low": 4900,
            "close": 4920,
            "pct_chg": -1.6,
        }]


def test_provider_benchmark_is_normalized_and_persisted(tmp_path) -> None:
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    points = MarketContextService(
        provider=FakeIndexProvider(), repository=repository
    ).refresh_provider_index(
        definition=BROAD_MARKET,
        start_date="2026-07-20",
        end_date="2026-07-20",
    )

    assert points[0].trade_date == "2026-07-20"
    assert points[0].pct_change == -1.6
    assert repository.bounds("csi_all_share") == ("2026-07-20", "2026-07-20", 1)


def test_benchmark_methodology_cannot_change_in_place(tmp_path) -> None:
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    service = MarketContextService(provider=FakeIndexProvider(), repository=repository)
    points = service.refresh_provider_index(
        definition=BROAD_MARKET,
        start_date="2026-07-20",
        end_date="2026-07-20",
    )
    changed = BenchmarkDefinition(
        **{**BROAD_MARKET.model_dump(), "methodology_version": "silently_changed"}
    )

    try:
        repository.upsert(definition=changed, points=points)
    except ValueError as exc:
        assert "新的 benchmark_id" in str(exc)
    else:
        raise AssertionError("frozen benchmark definition must not change in place")
