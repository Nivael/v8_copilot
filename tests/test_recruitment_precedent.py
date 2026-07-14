from __future__ import annotations

import sqlite3

from recruitment_precedent import (
    RecruitmentDeadlineCase,
    analyze_recruitment_precedents,
    extract_recruitment_deadline,
)


def test_extract_recruitment_deadline_prefers_application_context() -> None:
    text = (
        "公司于2024年8月2日启动预重整。"
        "报名阶段：意向投资人应自本公告发布之日起至2024年9月19日18时前，"
        "将报名材料发送至指定邮箱。公司于2024年9月6日披露本公告。"
    )

    assert extract_recruitment_deadline(text, "2024-09-05") == "2024-09-19"


def test_analyze_recruitment_precedents_uses_adjacent_trading_days(tmp_path) -> None:
    database = tmp_path / "research.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text, trade_date text, adjust text, close real, pct_change real
            );
            create table st_status_history (
                symbol text, start_date text, end_date text, status_name text
            );
        """)
        connection.execute(
            "insert into st_status_history values (?,?,?,?)",
            ("000001", "2024-01-01", None, "*ST样本"),
        )
        connection.executemany(
            "insert into daily_prices values (?,?,?,?,?)",
            [
                ("000001", "2024-01-02", "qfq", 10.0, 0.0),
                ("000001", "2024-01-03", "qfq", 9.5, -5.0),
                ("000001", "2024-01-04", "qfq", 9.03, -4.95),
                ("000001", "2024-01-05", "qfq", 9.10, 0.78),
            ],
        )
    cases = [RecruitmentDeadlineCase(
        announcement_id="123",
        symbol="000001",
        announcement_date="2024-01-02",
        title="关于公开招募重整投资人的公告",
        recruitment_deadline="2024-01-05",
        source_url="https://static.cninfo.com.cn/finalpage/2024-01-02/123.PDF",
        stock_name="*ST样本",
    )]

    precedents, counts = analyze_recruitment_precedents(
        database, cases, price_as_of="2024-01-05"
    )

    assert counts["price_covered_cases"] == 1
    assert counts["precedent_cases"] == 1
    assert precedents[0]["run_dates"] == ["2024-01-03", "2024-01-04"]
    assert precedents[0]["run_length"] == 2


def test_non_adjacent_limit_down_days_are_not_a_consecutive_precedent(tmp_path) -> None:
    database = tmp_path / "research.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text, trade_date text, adjust text, close real, pct_change real
            );
            create table st_status_history (
                symbol text, start_date text, end_date text, status_name text
            );
            insert into st_status_history values ('000001','2024-01-01',null,'ST样本');
            insert into daily_prices values ('000001','2024-01-02','qfq',9.5,-5.0);
            insert into daily_prices values ('000001','2024-01-03','qfq',9.6,1.05);
            insert into daily_prices values ('000001','2024-01-04','qfq',9.12,-5.0);
        """)
    case = RecruitmentDeadlineCase(
        announcement_id="123",
        symbol="000001",
        announcement_date="2024-01-02",
        title="公开招募重整投资人",
        recruitment_deadline="2024-01-04",
        source_url="https://static.cninfo.com.cn/finalpage/2024-01-02/123.PDF",
    )

    precedents, counts = analyze_recruitment_precedents(
        database, [case], price_as_of="2024-01-04"
    )

    assert counts["price_covered_cases"] == 1
    assert precedents == []
