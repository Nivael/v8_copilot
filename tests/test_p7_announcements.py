from __future__ import annotations

import sqlite3

from p7_announcements import (
    build_announcement_run,
    classify_announcement,
    classify_hard_event,
)


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table company_announcements (
                announcement_id text, symbol text, announcement_date text,
                title text, announcement_type text, url text, source text,
                body_text text
            );
            insert into company_announcements values
                ('A1','000001','2026-01-02','关于法院裁定受理公司重整的公告','公告','https://example/A1','cninfo',null),
                ('A2','000001','2026-01-03','关于公司预重整事项的进展公告','公告','https://example/A2','cninfo',null),
                ('A3','000002','2026-01-03','关于申请撤销退市风险警示的公告','公告','https://example/A3','cninfo',null),
                ('A4','000002','2026-01-04','关于撤销退市风险警示暨停牌的公告','公告','https://example/A4','cninfo',null);
        """)


def test_taxonomy_and_hard_event_rules_reject_progress_and_applications(tmp_path):
    assert classify_announcement("关于法院裁定受理公司重整的公告")[0] == "restructuring_and_pre_restructuring"
    assert classify_hard_event("关于公司预重整事项的进展公告")[0] == ""
    assert classify_hard_event("关于申请撤销退市风险警示的公告")[0] == ""
    assert classify_hard_event("关于撤销退市风险警示暨停牌的公告")[0] == "risk_warning_removed"

    database = tmp_path / "base.sqlite3"
    refresh = tmp_path / "refresh"
    refresh.mkdir()
    _database(database)
    run = build_announcement_run(
        base_database=database, refresh_directory=refresh,
        start_date="2026-01-01", through="2026-01-31",
    )
    assert run.announcement_count == 4
    assert run.hard_transition_count == 2
    progress = next(item for item in run.facts if item.announcement_id == "A2")
    application = next(item for item in run.facts if item.announcement_id == "A3")
    assert progress.not_hard_outcome is True
    assert application.not_hard_outcome is True
