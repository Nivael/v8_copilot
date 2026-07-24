from __future__ import annotations

import json
import sqlite3

import pytest

from p6b_dry_plan import (
    build_p6b_dry_plan,
    main,
    render_p6b_dry_plan_markdown,
)


DATES = [
    "2021-03-17",
    "2021-03-18",
    "2021-03-19",
    "2021-03-22",
    "2021-03-23",
    "2021-03-24",
]


def _base_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text,
                trade_date text,
                adjust text,
                close real
            );
            create table st_status_history (
                symbol text,
                start_date text,
                end_date text,
                status_name text,
                status_type text
            );
            create table st_status_history_evidence (
                symbol text,
                start_date text,
                evidence_status text
            );
            create table trading_status_daily (
                symbol text,
                trade_date text,
                is_suspended integer
            );
            insert into daily_prices values
                ('000001','2021-03-16','qfq',10),
                ('000001','2021-03-17','qfq',9),
                ('000001','2021-03-18','qfq',8),
                ('000001','2021-03-19','qfq',8),
                ('000001','2021-03-23','qfq',7),
                ('000002','2021-03-16','qfq',5),
                ('000002','2021-03-17','qfq',5),
                ('000002','2021-03-18','qfq',5),
                ('000002','2021-03-19','qfq',5),
                ('000002','2021-03-22','qfq',5),
                ('000002','2021-03-23','qfq',5),
                ('000002','2021-03-24','qfq',5);
            insert into st_status_history values
                ('000001','2021-03-17',null,'*ST样本','*ST'),
                ('000002','2021-03-17','2021-03-24','ST样本','ST'),
                ('000003','2021-03-20','2021-03-20','退市','delisted');
            insert into st_status_history_evidence values
                ('000001','2021-03-17','missing_evidence'),
                ('000002','2021-03-17','matched');
        """)


def _market_context_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table st_membership_daily (
                trade_date text,
                symbol text
            );
            create table benchmark_daily (
                benchmark_id text,
                trade_date text
            );
        """)
        connection.executemany(
            "insert into benchmark_daily values (?,?)",
            [
                (benchmark, day)
                for benchmark in ("csi_all_share", "st_equal_weight_v1")
                for day in DATES
            ],
        )
        connection.executemany(
            "insert into st_membership_daily values (?,?)",
            [
                *[(day, "000002") for day in DATES],
                ("2021-03-17", "000001"),
                ("2021-03-18", "000001"),
                ("2021-03-22", "000001"),
                ("2021-03-23", "000001"),
                ("2021-03-24", "000001"),
            ],
        )


def _market_factor_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "create table market_factor_snapshots (trade_date text)"
        )
        connection.execute(
            "insert into market_factor_snapshots values ('2021-03-17')"
        )


def _m6(index_path, manifest_path) -> None:
    records = [
        {
            "symbol": "000001",
            "episode_type": "restructuring_path",
            "evidence_status": "case_note_only",
            "window": {
                "start_date": "2021-03-22",
                "end_date": "2021-03-23",
            },
            "anchor_events": [],
        },
        {
            "symbol": "000001",
            "episode_type": "capital_structure_adjustment_path",
            "evidence_status": "case_note_only",
            "window": {
                "start_date": "2021-03-23",
                "end_date": "2021-03-23",
            },
            "anchor_events": [],
        },
        {
            "symbol": "000003",
            "episode_type": "delisting_terminal_path",
            "evidence_status": "case_note_only",
            "window": {
                "start_date": "2021-03-20",
                "end_date": "2021-03-20",
            },
            "anchor_events": [],
        },
    ]
    index_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps({
        "c09_discipline": {"records_with_exact_adjuster_fields": 0}
    }), encoding="utf-8")


def _fixture(tmp_path):
    base = tmp_path / "base.sqlite3"
    context = tmp_path / "context.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    index = tmp_path / "episodes.jsonl"
    manifest = tmp_path / "manifest.json"
    _base_database(base)
    _market_context_database(context)
    _market_factor_database(factors)
    _m6(index, manifest)
    return base, context, factors, index, manifest


def test_plan_builds_continuous_membership_episodes_and_date_only_requests(
    tmp_path,
) -> None:
    base, context, factors, index, manifest = _fixture(tmp_path)
    source_stats = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in (base, context, factors, index, manifest)
    }

    plan = build_p6b_dry_plan(
        base_database=base,
        market_context_database=context,
        market_factor_database=factors,
        episode_index=index,
        episode_manifest=manifest,
        as_of="2021-03-24",
    )

    assert plan.episode_summary.episode_count == 3
    assert plan.episode_summary.symbol_count == 2
    assert plan.episode_summary.repeated_symbol_count == 1
    assert plan.episode_summary.open_episode_count == 2
    assert plan.episode_summary.membership_calendar_gap_count == 0
    assert plan.market_cap_requests.unique_trade_date_count == 2
    assert plan.market_cap_requests.request_basis.endswith("per_trade_date")
    assert plan.market_cap_requests.benchmark_date_ranges == {
        "csi_all_share": "2021-03-17..2021-03-24",
        "st_equal_weight_v1": "2021-03-17..2021-03-24",
    }
    assert all(day >= "2021-03-17" for day in plan.market_cap_requests.probe_trade_dates)
    assert plan.status_history_audit.open_row_count == 1
    assert (
        plan.status_history_audit.status_history_usable_as_primary_episode_source
        is False
    )
    assert plan.m6_candidates.restructuring_records == 1
    assert plan.m6_candidates.capital_structure_records == 1
    assert plan.episode_summary.m6_restructuring_candidate_episode_count == 1
    second = next(
        item for item in plan.episodes
        if item.symbol == "000001" and item.start_date == "2021-03-22"
    )
    assert second.start_price_lag_trading_days == 1
    assert second.repricing_anchor_date == "2021-03-19"
    assert plan.capital_and_terminal_audit.historical_share_change_guard_available is False
    assert any("股本变化" in item for item in plan.next_phase_blockers)
    assert any("95%" in item for item in plan.next_phase_blockers)
    assert all(
        (path.stat().st_size, path.stat().st_mtime_ns) == stats
        for path, stats in source_stats.items()
    )


def test_membership_calendar_gap_does_not_create_false_episode_exit(tmp_path) -> None:
    base, context, factors, index, manifest = _fixture(tmp_path)
    with sqlite3.connect(context) as connection:
        connection.execute(
            "delete from st_membership_daily where trade_date='2021-03-19'"
        )

    plan = build_p6b_dry_plan(
        base_database=base,
        market_context_database=context,
        market_factor_database=factors,
        episode_index=index,
        episode_manifest=manifest,
    )

    always_member = [
        item for item in plan.episodes if item.symbol == "000002"
    ]
    assert len(always_member) == 1
    assert always_member[0].start_date == "2021-03-17"
    assert always_member[0].end_date == "2021-03-24"
    assert always_member[0].boundary_gap_adjacent is False
    assert plan.episode_summary.membership_calendar_gap_count == 1


def test_markdown_is_one_page_decision_summary(tmp_path) -> None:
    base, context, factors, index, manifest = _fixture(tmp_path)
    plan = build_p6b_dry_plan(
        base_database=base,
        market_context_database=context,
        market_factor_database=factors,
        episode_index=index,
        episode_manifest=manifest,
    )

    markdown = render_p6b_dry_plan_markdown(plan)

    assert "# P6B-0 只读 dry plan" in markdown
    assert "人类只需确认" in markdown
    assert "symbol × date" in markdown
    assert "不联网、不修改生产数据库" in markdown


def test_cli_writes_only_explicit_report_outputs(tmp_path) -> None:
    base, context, factors, index, manifest = _fixture(tmp_path)
    output_json = tmp_path / "out" / "plan.json"
    output_markdown = tmp_path / "out" / "plan.md"

    result = main([
        "--base-database", str(base),
        "--market-context-database", str(context),
        "--market-factor-database", str(factors),
        "--episode-index", str(index),
        "--episode-manifest", str(manifest),
        "--output-json", str(output_json),
        "--output-markdown", str(output_markdown),
    ])

    assert result == 0
    assert json.loads(output_json.read_text(encoding="utf-8"))["contract_version"] == (
        "v8_p6b_dry_plan_v1"
    )
    assert "价格可用性代理" in output_markdown.read_text(encoding="utf-8")
    assert not list(tmp_path.rglob("*-journal"))


def test_missing_source_fails_without_creating_database(tmp_path) -> None:
    base, context, factors, index, manifest = _fixture(tmp_path)
    missing = tmp_path / "missing.sqlite3"

    with pytest.raises(FileNotFoundError):
        build_p6b_dry_plan(
            base_database=missing,
            market_context_database=context,
            market_factor_database=factors,
            episode_index=index,
            episode_manifest=manifest,
        )

    assert not missing.exists()
