from __future__ import annotations

import json
import os
import sqlite3

import pytest

from p6b_provider_probe import (
    _load_provider_env,
    build_provider_probe,
    render_provider_probe_markdown,
)


PROBE_DATES = ("2024-04-29", "2025-04-30")
EPISODE_ID = (
    "episode:SZ000001:capital_structure_adjustment_path:"
    "2024-01-01:test"
)


class FakeProvider:
    def __init__(self, *, failing_date: str = ""):
        self.failing_date = failing_date
        self.date_calls: list[str] = []
        self.range_calls: list[tuple[str, str, str]] = []

    def fetch_daily_basic(self, *, trade_date: str):
        self.date_calls.append(trade_date)
        if trade_date == self.failing_date:
            raise RuntimeError("test provider failure")
        compact = trade_date.replace("-", "")
        return [
            {
                "ts_code": "000001.SZ",
                "trade_date": compact,
                "total_share": 10,
                "float_share": 8,
                "free_share": 7,
                "total_mv": 100,
                "circ_mv": 80,
                "turnover_rate": 1,
            },
            {
                "ts_code": "000002.SZ",
                "trade_date": compact,
                "total_share": 20,
                "float_share": 18,
                "free_share": 17,
                "total_mv": 200,
                "circ_mv": 180,
                "turnover_rate": 1,
            },
        ]

    def fetch_daily_basic_range(
        self, *, symbol: str, start_date: str, end_date: str
    ):
        self.range_calls.append((symbol, start_date, end_date))
        return [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "total_share": 10,
            },
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240110",
                "total_share": 15,
            },
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240111",
                "total_share": 15,
            },
        ]


def _market_context(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "create table st_membership_daily "
            "(trade_date text not null,symbol text not null)"
        )
        connection.executemany(
            "insert into st_membership_daily values (?,?)",
            [
                (day, symbol)
                for day in PROBE_DATES
                for symbol in ("000001", "000002")
            ],
        )


def _episode_index(path) -> None:
    path.write_text(json.dumps({
        "episode_id": EPISODE_ID,
        "episode_type": "capital_structure_adjustment_path",
        "symbol": "000001",
        "stock_name": "*ST测试",
        "window": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
        "anchor_events": [
            {"anchor_date": "2024-01-09"},
        ],
    }) + "\n", encoding="utf-8")


def test_probe_accepts_scoped_backfill_and_keeps_stale_disabled(tmp_path) -> None:
    context = tmp_path / "context.sqlite3"
    episodes = tmp_path / "episodes.jsonl"
    _market_context(context)
    _episode_index(episodes)
    source_stats = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in (context, episodes)
    }
    provider = FakeProvider()

    result = build_provider_probe(
        provider=provider,
        market_context_database=context,
        episode_index=episodes,
        probe_dates=PROBE_DATES,
        capital_episode_ids=(EPISODE_ID,),
        as_of="2025-04-30",
    )

    assert result.overall_status == "ready_for_scoped_backfill"
    assert result.exact_ready_date_count == 2
    assert result.provider_history_available_from == "2024-04-29"
    assert result.single_publishable_history_boundary == "2024-04-29"
    assert result.recommended_backfill_start == "2024-04-29"
    assert provider.date_calls == list(PROBE_DATES)
    assert provider.range_calls == [
        ("000001", "2024-01-01", "2024-01-31")
    ]
    assert result.capital_history[0].share_changes[0].trade_date == "2024-01-10"
    assert result.capital_history[0].share_changes[0].change_ratio == 0.5
    stale = next(
        item for item in result.decisions
        if item.decision_id == "stale_market_cap_policy"
    )
    assert stale.status == "accepted_safe_default"
    assert "默认不使用陈旧市值" in stale.recommendation
    assert all(
        (path.stat().st_size, path.stat().st_mtime_ns) == stats
        for path, stats in source_stats.items()
    )


def test_probe_does_not_infer_continuous_boundary_from_mixed_dates(
    tmp_path,
) -> None:
    context = tmp_path / "context.sqlite3"
    episodes = tmp_path / "episodes.jsonl"
    _market_context(context)
    _episode_index(episodes)

    result = build_provider_probe(
        provider=FakeProvider(failing_date=PROBE_DATES[0]),
        market_context_database=context,
        episode_index=episodes,
        probe_dates=PROBE_DATES,
        capital_episode_ids=(EPISODE_ID,),
        as_of="2025-04-30",
    )

    assert result.overall_status == "partial"
    assert result.cross_sections[0].status == "provider_error"
    assert result.provider_history_available_from == ""
    assert result.single_publishable_history_boundary == ""


def test_probe_fails_loudly_when_frozen_capital_episode_is_missing(
    tmp_path,
) -> None:
    context = tmp_path / "context.sqlite3"
    episodes = tmp_path / "episodes.jsonl"
    _market_context(context)
    episodes.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="缺冻结 capital probe episode"):
        build_provider_probe(
            provider=FakeProvider(),
            market_context_database=context,
            episode_index=episodes,
            probe_dates=PROBE_DATES,
            capital_episode_ids=(EPISODE_ID,),
            as_of="2025-04-30",
        )


def test_probe_markdown_is_one_page_release_summary(tmp_path) -> None:
    context = tmp_path / "context.sqlite3"
    episodes = tmp_path / "episodes.jsonl"
    _market_context(context)
    _episode_index(episodes)
    result = build_provider_probe(
        provider=FakeProvider(),
        market_context_database=context,
        episode_index=episodes,
        probe_dates=PROBE_DATES,
        capital_episode_ids=(EPISODE_ID,),
        as_of="2025-04-30",
    )

    markdown = render_provider_probe_markdown(result)

    assert "# P6B provider probe" in markdown
    assert "11 个冻结截面" in markdown
    assert "自动采用的安全决定" in markdown
    assert "ready_for_scoped_backfill" in markdown


def test_probe_env_loader_ignores_unrelated_secrets(
    tmp_path, monkeypatch
) -> None:
    env_file = tmp_path / "provider.env"
    env_file.write_text(
        "TUSHARE_TOKEN=test-token\n"
        "TUSHARE_HTTP_URL=https://example.test\n"
        "XUEQIU_COOKIE=must-not-load\n",
        encoding="utf-8",
    )
    for key in ("TUSHARE_TOKEN", "TUSHARE_HTTP_URL", "XUEQIU_COOKIE"):
        monkeypatch.delenv(key, raising=False)

    _load_provider_env(env_file)

    assert os.environ["TUSHARE_TOKEN"] == "test-token"
    assert os.environ["TUSHARE_HTTP_URL"] == "https://example.test"
    assert "XUEQIU_COOKIE" not in os.environ
