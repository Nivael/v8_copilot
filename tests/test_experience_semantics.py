import sqlite3
from copy import deepcopy

import pytest
from types import SimpleNamespace

import answer_engine
from p7_announcements import build_announcement_run
from market_comparison import MarketComparisonWindow


def history_inputs(tmp_path, monkeypatch):
    database = tmp_path / "history.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("create table company_announcements(symbol,announcement_date,title,announcement_id)")
        connection.executemany("insert into company_announcements values (?,?,?,?)", [
            ("000001", "2026-01-05", "关于法院裁定受理公司重整的公告", "A1"),
            ("000002", "2026-01-05", "关于子公司重整的公告", "A2"),
        ])
    episodes = [
        {"episode_id": "E1", "symbol": "000001", "episode_type": "restructuring_path", "anchor_events": [
            {"announcement_date": "2026-01-01", "title": "关于公司预重整进展的公告"},
            {"announcement_date": "2026-01-03", "title": "关于公司预重整进展的公告"},
            {"announcement_date": "2026-01-05", "title": "关于法院裁定受理公司重整的公告"},
        ]},
        {"episode_id": "E2", "symbol": "000002", "episode_type": "restructuring_path", "anchor_events": [
            {"announcement_date": "2026-01-01", "title": "关于公司预重整进展的公告"},
            {"announcement_date": "2026-01-05", "title": "关于法院裁定受理子公司重整的公告"},
        ]},
    ]
    monkeypatch.setattr(answer_engine, "BASE_DB", database)
    monkeypatch.setattr(answer_engine, "_iter_episodes", lambda *_: iter(episodes))
    return episodes


def test_history_dedupes_cases_and_keeps_unobserved_followups(tmp_path, monkeypatch):
    episodes = history_inputs(tmp_path, monkeypatch)
    episodes.append(deepcopy(episodes[0]))
    rows = answer_engine._historical_next_restructuring_rows("预重整工作推进中")
    stage = next(row for row in rows if row["后续口径"] == "下一个不同重整阶段")
    assert stage["起点事件总数"] == 2
    assert stage["可观察后续总数"] == 1
    assert stage["未观察到后续"] == 1
    assert stage["次数"] == 1
    assert stage["等待中位数(天)"] == 2  # last same-stage notice, not the first notice


def test_conflicting_duplicate_case_fails_instead_of_choosing_an_outcome(tmp_path, monkeypatch):
    episodes = history_inputs(tmp_path, monkeypatch)
    changed = deepcopy(episodes[0])
    changed["anchor_events"][-1]["title"] = "关于公开招募重整投资人的公告"
    episodes.append(changed)
    with pytest.raises(ValueError, match="同一历史起点"):
        answer_engine._historical_next_restructuring_rows("预重整工作推进中")


def test_same_day_bundles_keep_issuer_date_and_sources_separate(tmp_path):
    database = tmp_path / "announcements.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("create table company_announcements(announcement_id,symbol,announcement_date,title,announcement_type,url,source,body_text)")
        connection.executemany("insert into company_announcements values (?,?,?,?,?,?,?,?)", [
            ("A1", "000001", "2026-01-02", "关于公司预重整事项的公告", "公告", "https://example.invalid/A1", "cninfo", None),
            ("A2", "000001", "2026-01-02", "关于公司预重整事项的补充公告", "公告", "https://example.invalid/A2", "cninfo", None),
            ("A3", "000002", "2026-01-02", "关于公司预重整事项的公告", "公告", "https://example.invalid/A3", "cninfo", None),
            ("A4", "000001", "2026-01-03", "关于公司预重整事项的公告", "公告", "https://example.invalid/A4", "cninfo", None),
        ])
    refresh = tmp_path / "refresh"
    refresh.mkdir()
    run = build_announcement_run(base_database=database, refresh_directory=refresh,
                                 start_date="2026-01-01", through="2026-01-31")
    bundle = next(row for row in run.bundles if row.symbol == "000001" and row.announcement_date == "2026-01-02")
    assert set(bundle.announcement_ids) == {"A1", "A2"}
    assert len(bundle.source_urls) == 2
    assert run.bundle_count == 3


def test_unavailable_market_window_cannot_claim_a_factor_snapshot(monkeypatch):
    def forbidden_lookup(**kwargs):
        raise AssertionError("factor query must wait for a valid market window")
    monkeypatch.setattr(answer_engine, "load_microcap_comparison", forbidden_lookup)
    card = SimpleNamespace(body_rows=[], analysis_claims=[], provenance=[])
    result = answer_engine._attach_microcap_comparison(card, market_window=MarketComparisonWindow(
        status="gaps", symbol=None, sessions=10, gaps=["different source endpoints"],
    ))
    assert result is None
    assert card.body_rows[0]["factor_lookup_executed"] is False
    assert card.body_rows[0]["factor_snapshot_id"] == "unavailable"
    assert card.provenance == []
