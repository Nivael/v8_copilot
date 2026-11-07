import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from valuation_episodes import (
    _load_title_events,
    _stage_episode,
    build_verified_episodes,
    classify_official_title,
)


def event(kind, day):
    from valuation_episodes import VerifiedEvent

    return VerifiedEvent(
        event_id=f"E-{kind}-{day}",
        symbol="000001",
        event_type=kind,
        event_date=day,
        information_available_date=day,
        source_kind="official_title_exact",
        source_ref=f"cninfo:{kind}:{day}",
        title=kind,
    )


def candidate(symbol, start, end, number):
    return SimpleNamespace(
        episode_id=f"C-{symbol}-{number}",
        symbol=symbol,
        start_date=start,
        end_date=end,
        is_open=False,
        m6_restructuring_candidate_count=0,
    )


def base_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            create table st_status_history (
                symbol text, start_date text, end_date text, status_type text,
                status_name text
            );
            create table company_announcements (
                announcement_id text, symbol text, announcement_date text,
                title text, url text
            );
            create table stocks_meta (symbol text, name text);
            create table name_changes (
                symbol text, old_name text, new_name text
            );
            """
        )
        connection.executemany(
            "insert into stocks_meta values (?,?)",
            [("000001", "ST测试一"), ("000002", "ST测试二")],
        )
        connection.execute(
            "insert into st_status_history values "
            "('000001','2026-01-02','2026-01-12','other','测试一:ST')"
        )
        connection.execute(
            "insert into st_status_history values "
            "('000002','2026-01-02','2026-01-05','other','测试二:ST')"
        )
        connection.execute(
            "insert into st_status_history values "
            "('000002','2026-01-09','2026-01-12','other','测试二:ST')"
        )
        rows = [
            ("A1", "000001", "2026-01-03", "关于拟向法院申请破产重整事项的公告"),
            ("A2", "000001", "2026-01-04", "关于收到预重整决定书的公告"),
            ("A3", "000001", "2026-01-08", "关于终止预重整和重整事项的公告"),
            ("B0", "000002", "2026-01-09", "其他公司重整计划（草案）"),
            ("B1", "000002", "2026-01-10", "重整计划（草案）"),
            ("B2", "000002", "2026-01-11", "关于重整计划执行完毕的公告"),
        ]
        connection.executemany(
            "insert into company_announcements values (?,?,?,?, '')", rows
        )


def market_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "create table benchmark_daily (benchmark_id text,trade_date text)"
        )
        for day in range(2, 13):
            connection.execute(
                "insert into benchmark_daily values ('csi_all_share',?)",
                (f"2026-01-{day:02d}",),
            )


def test_exact_title_classifier_rejects_related_entity_and_progress_noise():
    assert (
        classify_official_title("关于公司收到法院终结预重整决定书暨终止预重整事项的公告")
        == "restructuring_terminated"
    )
    assert classify_official_title("关于子公司被法院裁定受理重整的公告") is None
    assert classify_official_title("重整及预重整事项的进展公告") is None
    assert classify_official_title("关于延期提交重整计划草案的公告") is None
    assert classify_official_title("关于三个月不计入提交重整计划草案期限的公告") is None
    assert (
        classify_official_title("某某股份有限公司重整计划草案")
        == "restructuring_plan_published"
    )


_COURT_TITLE_CASES = json.loads(
    (Path(__file__).parents[1] / "evals/fixtures/node_title_court_scope_v1.json").read_text()
)["cases"]


@pytest.mark.parametrize("case", _COURT_TITLE_CASES, ids=lambda case: case["announcement_id"])
def test_public_court_title_regressions(case):
    assert classify_official_title(case["title"]) == case["expected_title_classification"]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("关于法院裁定受理公司重整暨申请撤销因内部控制缺陷而被实施的其他风险警示的公告", "formal_restructuring_accepted"),
        ("关于因法院裁定受理公司重整而被实施退市风险警示暨撤销其他风险警示的公告", "formal_restructuring_accepted"),
        ("关于申请撤销因法院裁定受理公司重整而被实施的退市风险警示暨重整计划执行完毕的公告", "restructuring_completed"),
        ("关于申请撤销因法院裁定受理公司重整而被实施的退市风险警示暨法院裁定批准重整计划的公告", "restructuring_plan_approved"),
        ("关于申请撤销由于法院裁定受理公司重整所导致的退市风险警示的公告", None),
        ("关于法院裁定受理公司重整的公告（已撤回）", None),
        ("关于法院裁定受理公司重整的公告(已撤销)", None),
        ("预重整计划草案之出资人权益调整方案（已取消）", None),
        (" 关于法院裁定受理公司重整\n的公告 （更新后） ", "formal_restructuring_accepted"),
    ],
)
def test_warning_cause_removal_preserves_separate_current_events(title, expected):
    assert classify_official_title(title) == expected


def test_title_event_loader_omits_old_warning_causes_without_dropping_new_acceptance(tmp_path):
    database = tmp_path / "base.db"
    base_database(database)
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "insert into company_announcements values (?,?,?,?, '')",
            [(case["announcement_id"], "000001", "2026-01-05", case["title"]) for case in _COURT_TITLE_CASES],
        )
    events = _load_title_events(database, as_of="2026-01-12")
    actual = {event.source_ref: event.event_type for event in events}
    for case in _COURT_TITLE_CASES:
        ref = f"cninfo:{case['announcement_id']}"
        if case["expected_title_classification"] is None:
            assert ref not in actual
        else:
            assert actual[ref] == case["expected_title_classification"]


def test_termination_resets_current_stage_without_losing_maximum():
    current, maximum, procedure, boundary, inputs, outcomes, conflicts = _stage_episode(
        symbol="000001",
        start="2026-01-01",
        end="2026-01-10",
        events=[
            event("restructuring_application_disclosed", "2026-01-02"),
            event("pre_restructuring_started", "2026-01-03"),
            event("restructuring_terminated", "2026-01-04"),
        ],
    )
    assert current == "st_distress_only"
    assert maximum == "pre_restructuring_started"
    assert procedure == "terminated"
    assert not boundary
    assert len(inputs) == 3
    assert outcomes == []
    assert conflicts == []


def test_plan_boundary_stops_p6b_input_but_keeps_outcome():
    plan = event("restructuring_plan_published", "2026-01-05")
    completed = event("restructuring_completed", "2026-01-08")
    current, _, procedure, boundary, inputs, outcomes, _ = _stage_episode(
        symbol="000001",
        start="2026-01-01",
        end="2026-01-10",
        events=[plan, completed],
    )
    assert current == "plan_key_terms_disclosed"
    assert procedure == "plan_boundary_reached"
    assert boundary == "2026-01-05"
    assert [item.event_type for item in inputs] == ["restructuring_plan_published"]
    assert [item.event_type for item in outcomes] == ["restructuring_completed"]


def test_short_membership_gap_merges_only_with_continuous_status(tmp_path):
    base = tmp_path / "base.sqlite3"
    market = tmp_path / "market.sqlite3"
    base_database(base)
    market_database(market)
    dry_plan = SimpleNamespace(
        episodes=[
            candidate("000001", "2026-01-02", "2026-01-05", 1),
            candidate("000001", "2026-01-07", "2026-01-12", 2),
            candidate("000002", "2026-01-02", "2026-01-05", 1),
            candidate("000002", "2026-01-09", "2026-01-12", 2),
        ]
    )
    episodes, _, _, _ = build_verified_episodes(
        dry_plan=dry_plan,
        base_database=base,
        market_context_database=market,
        p6a_database=tmp_path / "missing.sqlite3",
        as_of="2026-01-12",
    )
    first = [item for item in episodes if item.symbol == "000001"]
    repeated = [item for item in episodes if item.symbol == "000002"]
    assert len(first) == 1
    assert first[0].component_candidate_ids == ["C-000001-1", "C-000001-2"]
    assert first[0].merged_membership_gap_trade_days == 1
    assert first[0].current_stage == "st_distress_only"
    assert first[0].max_stage_reached == "pre_restructuring_started"
    assert first[0].procedure_status == "terminated"
    assert len(repeated) == 2


def test_plan_event_in_second_repeated_episode_does_not_leak_backward(tmp_path):
    base = tmp_path / "base.sqlite3"
    market = tmp_path / "market.sqlite3"
    base_database(base)
    market_database(market)
    dry_plan = SimpleNamespace(
        episodes=[
            candidate("000002", "2026-01-02", "2026-01-05", 1),
            candidate("000002", "2026-01-09", "2026-01-12", 2),
        ]
    )
    episodes, _, _, _ = build_verified_episodes(
        dry_plan=dry_plan,
        base_database=base,
        market_context_database=market,
        p6a_database=tmp_path / "missing.sqlite3",
        as_of="2026-01-12",
    )
    assert episodes[0].current_stage == "st_distress_only"
    assert episodes[0].p6c_boundary_date == ""
    assert episodes[1].current_stage == "plan_key_terms_disclosed"
    assert episodes[1].p6c_boundary_date == "2026-01-10"
    assert [item.event_type for item in episodes[1].outcome_events] == [
        "restructuring_completed"
    ]
