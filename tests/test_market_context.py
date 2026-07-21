from __future__ import annotations

import sqlite3

from market_context import (
    BROAD_MARKET,
    CANONICAL_BENCHMARK_POOL,
    CSI_2000,
    BenchmarkDefinition,
    BenchmarkPoint,
    HistoricalStMembershipService,
    MarketContextRepository,
    MarketContextService,
    build_market_context_manifest,
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


class FakeCsi2000Provider:
    def fetch_index_daily(self, *, ts_code: str, start_date: str, end_date: str):
        assert ts_code == "932000.CSI"
        return [{
            "ts_code": ts_code,
            "trade_date": "20260720",
            "open": 3200,
            "high": 3210,
            "low": 3100,
            "close": 3120,
            "pct_chg": -2.5,
        }]


def test_csi_2000_is_a_canonical_size_reference_in_the_same_pool(tmp_path) -> None:
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    points = MarketContextService(
        provider=FakeCsi2000Provider(), repository=repository
    ).refresh_provider_index(
        definition=CSI_2000,
        start_date="2026-07-20",
        end_date="2026-07-20",
    )

    assert points[0].benchmark_id == "csi_2000"
    assert repository.bounds("csi_2000") == ("2026-07-20", "2026-07-20", 1)
    assert [item.benchmark_id for item in CANONICAL_BENCHMARK_POOL] == [
        "st_equal_weight_v1", "csi_2000", "csi_all_share",
    ]
    assert CSI_2000.kind == "size"
    assert "净流入" in "".join(CSI_2000.notes)


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


class FakeMembershipProvider:
    def __init__(self, rows):
        self.rows = rows
        self.offsets = []

    def fetch_st_universe_range(
        self, *, start_date: str, end_date: str, limit: int, offset: int
    ):
        self.offsets.append(offset)
        return self.rows[offset:offset + limit]


def _membership_row(day: str, symbol: str) -> dict:
    return {
        "ts_code": f"{symbol}.SZ",
        "name": f"ST {symbol}",
        "trade_date": day.replace("-", ""),
        "type": "ST",
        "type_name": "风险警示板",
    }


def test_historical_membership_backfill_resumes_by_offset(tmp_path) -> None:
    rows = [
        _membership_row("2026-07-20", "000001"),
        _membership_row("2026-07-20", "000002"),
        _membership_row("2026-07-17", "000001"),
    ]
    provider = FakeMembershipProvider(rows)
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    service = HistoricalStMembershipService(provider=provider, repository=repository)

    partial = service.backfill(
        start_date="2026-07-17", end_date="2026-07-20", page_size=2, max_pages=1
    )
    complete = service.backfill(
        start_date="2026-07-17", end_date="2026-07-20", page_size=2
    )

    assert partial.status == "partial"
    assert complete.status == "complete"
    assert provider.offsets == [0, 2]
    assert repository.membership_bounds() == ("2026-07-17", "2026-07-20", 3, 2)


def test_membership_backfill_migrates_an_existing_benchmark_only_database(tmp_path) -> None:
    path = tmp_path / "market.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "create table benchmark_definitions (benchmark_id text primary key, "
            "contract_version text, definition_json text, updated_at text)"
        )
    repository = MarketContextRepository(path)

    result = HistoricalStMembershipService(
        provider=FakeMembershipProvider([_membership_row("2026-07-20", "000001")]),
        repository=repository,
    ).backfill(start_date="2026-07-20", end_date="2026-07-20", page_size=10)

    assert result.status == "complete"
    assert repository.membership_bounds()[2:] == (1, 1)


def test_materialized_st_index_joins_daily_membership_to_qfq_returns(tmp_path) -> None:
    rows = [
        _membership_row("2026-07-17", "000001"),
        _membership_row("2026-07-17", "000002"),
        _membership_row("2026-07-20", "000001"),
        _membership_row("2026-07-20", "000002"),
    ]
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    HistoricalStMembershipService(
        provider=FakeMembershipProvider(rows), repository=repository
    ).backfill(start_date="2026-07-17", end_date="2026-07-20", page_size=10)
    prices = tmp_path / "prices.sqlite3"
    with sqlite3.connect(prices) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text, trade_date text, adjust text, pct_change real
            );
            insert into daily_prices values
                ('000001','2026-07-17','qfq',-2.0),
                ('000002','2026-07-17','qfq',0.0),
                ('000001','2026-07-20','qfq',-3.0);
        """)
    repository.upsert(definition=BROAD_MARKET, points=[
        BenchmarkPoint(
            benchmark_id=BROAD_MARKET.benchmark_id,
            trade_date="2026-07-17", close=5000,
            source=BROAD_MARKET.provider,
        ),
        BenchmarkPoint(
            benchmark_id=BROAD_MARKET.benchmark_id,
            trade_date="2026-07-20", close=4900,
            source=BROAD_MARKET.provider,
        ),
    ])

    points = repository.materialize_st_equal_weight(
        price_database=prices,
        start_date="2026-07-17",
        end_date="2026-07-20",
    )
    manifest = build_market_context_manifest(repository=repository)

    assert [point.pct_change for point in points] == [-1.0, -3.0]
    assert [point.coverage_ratio for point in points] == [1.0, 0.5]
    st = next(row for row in manifest["benchmarks"] if row["benchmark_id"] == "st_equal_weight_v1")
    assert st["ready_coverage_dates"] == 1
    assert manifest["membership"]["missing_trading_date_count"] == 0
    assert manifest["membership"]["pre_source_trading_dates"] == 0


def test_incremental_st_materialization_continues_prior_index_level(tmp_path) -> None:
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    repository.upsert(definition=BROAD_MARKET, points=[
        BenchmarkPoint(
            benchmark_id=BROAD_MARKET.benchmark_id,
            trade_date=day,
            close=5000,
            source=BROAD_MARKET.provider,
        )
        for day in ["2026-07-20", "2026-07-21"]
    ])
    rows = [
        _membership_row("2026-07-20", "000001"),
        _membership_row("2026-07-21", "000001"),
    ]
    HistoricalStMembershipService(
        provider=FakeMembershipProvider(rows), repository=repository
    ).backfill(start_date="2026-07-20", end_date="2026-07-21", page_size=10)
    prices = tmp_path / "prices.sqlite3"
    with sqlite3.connect(prices) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text, trade_date text, adjust text, pct_change real
            );
            insert into daily_prices values
                ('000001','2026-07-20','qfq',-10.0),
                ('000001','2026-07-21','qfq',10.0);
        """)

    first = repository.materialize_st_equal_weight(
        price_database=prices,
        start_date="2026-07-20",
        end_date="2026-07-20",
    )
    second = repository.materialize_st_equal_weight(
        price_database=prices,
        start_date="2026-07-21",
        end_date="2026-07-21",
    )

    assert first[0].close == 900.0
    assert second[0].close == 990.0


def test_market_manifest_requires_all_three_pool_references_for_current_ready(
    tmp_path,
) -> None:
    dates = [
        "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10",
        "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16",
        "2026-07-17", "2026-07-20",
    ]
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    repository.upsert(definition=BROAD_MARKET, points=[
        BenchmarkPoint(
            benchmark_id=BROAD_MARKET.benchmark_id,
            trade_date=day,
            close=5000,
            pct_change=-1,
            source=BROAD_MARKET.provider,
        )
        for day in dates
    ])
    HistoricalStMembershipService(
        provider=FakeMembershipProvider([
            _membership_row(day, "000001") for day in reversed(dates)
        ]),
        repository=repository,
    ).backfill(start_date=dates[0], end_date=dates[-1], page_size=100)
    prices = tmp_path / "prices.sqlite3"
    with sqlite3.connect(prices) as connection:
        connection.execute(
            "create table daily_prices "
            "(symbol text, trade_date text, adjust text, pct_change real)"
        )
        connection.executemany(
            "insert into daily_prices values ('000001',?,'qfq',-1.0)",
            [(day,) for day in dates],
        )
    repository.materialize_st_equal_weight(
        price_database=prices, start_date=dates[0], end_date=dates[-1]
    )

    before = build_market_context_manifest(repository=repository)
    repository.upsert(definition=CSI_2000, points=[
        BenchmarkPoint(
            benchmark_id=CSI_2000.benchmark_id,
            trade_date=day,
            close=3000,
            pct_change=-1.2,
            source=CSI_2000.provider,
        )
        for day in dates
    ])
    after = build_market_context_manifest(repository=repository)

    assert before["current_status"] == "gaps"
    assert after["current_status"] == "ready"
    assert after["current_required_benchmarks"] == [
        "st_equal_weight_v1", "csi_2000", "csi_all_share",
    ]
    assert [item["benchmark_id"] for item in after["benchmark_pool"]] == [
        "st_equal_weight_v1", "csi_2000", "csi_all_share",
    ]
    assert after["pool_common_window"] == {
        "start": "2026-07-07", "end": "2026-07-20",
    }


class DateMembershipProvider:
    def fetch_st_universe_range(
        self, *, start_date: str, end_date: str, limit: int, offset: int
    ):
        rows = [_membership_row(start_date, "000001")]
        return rows[offset:offset + limit]


def test_repair_fills_missing_benchmark_trading_date_but_ignores_weekend(tmp_path) -> None:
    repository = MarketContextRepository(tmp_path / "market.sqlite3")
    repository.upsert(definition=BROAD_MARKET, points=[
        BenchmarkPoint(
            benchmark_id=BROAD_MARKET.benchmark_id,
            trade_date="2026-07-20", close=4900,
            source=BROAD_MARKET.provider,
        ),
    ])
    service = HistoricalStMembershipService(
        provider=DateMembershipProvider(), repository=repository
    )
    # Weekend membership is preserved as source history, but is not a benchmark date.
    service.backfill(
        start_date="2026-07-19", end_date="2026-07-19", page_size=10
    )

    result = service.repair_trading_date_gaps(
        start_date="2026-07-19", end_date="2026-07-20"
    )

    assert result["requested_dates"] == ["2026-07-20"]
    assert result["repaired_dates"] == ["2026-07-20"]
    assert repository.missing_membership_trading_dates(
        start_date="2026-07-19", end_date="2026-07-20"
    ) == []
    build_market_context_manifest,
