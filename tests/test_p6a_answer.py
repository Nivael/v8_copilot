import sqlite3
from datetime import date, timedelta

import orchestrator as orchestrator_module
from answer_engine import card_stock_administrator_history
from api import orchestrate as api_orchestrate
from api_contract import ResearchRequest
from evals.deterministic_router_v0 import route_question
from restructuring_administrators import (
    AdministratorRepository,
    AnnouncementSourceRow,
    extract_administrator_appointment,
)


def _days(start: date, count: int) -> list[str]:
    result = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _sources(tmp_path):
    repository_database = tmp_path / "administrators.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    market = tmp_path / "market.sqlite3"
    body = (
        "江西沐邦高科股份有限公司关于法院决定启动预重整事项的公告。"
        "2025年2月10日，法院作出（2025）赣01破申19号决定书，"
        "指定北京市金杜（深圳）律师事务所担任公司预重整临时管理人。"
        "公司能否进入正式重整程序存在重大不确定性，敬请投资者注意风险。"
    ) * 3
    result = extract_administrator_appointment(AnnouncementSourceRow(
        announcement_id="P6A-1",
        symbol="603398",
        announcement_date=date(2025, 2, 10),
        title="关于法院决定启动预重整并指定临时管理人的公告",
        url="https://example.test/P6A-1",
        body_text=body,
        source="cninfo",
    ))
    AdministratorRepository(repository_database).persist(result)

    days = _days(date(2025, 1, 1), 100)
    with sqlite3.connect(prices) as connection:
        connection.execute(
            "create table daily_prices (symbol text,trade_date text,adjust text,close real)"
        )
        connection.executemany(
            "insert into daily_prices values (?,?,?,?)",
            [
                ("603398", day, "qfq", 10 + index * 0.05)
                for index, day in enumerate(days)
            ],
        )
    with sqlite3.connect(market) as connection:
        connection.execute(
            "create table benchmark_daily ("
            "benchmark_id text,trade_date text,close real,coverage_ratio real)"
        )
        for benchmark_id, base in (
            ("st_equal_weight_v1", 1000),
            ("csi_2000", 2000),
            ("csi_all_share", 3000),
        ):
            connection.executemany(
                "insert into benchmark_daily values (?,?,?,?)",
                [
                    (
                        benchmark_id,
                        day,
                        base + index,
                        1.0 if benchmark_id == "st_equal_weight_v1" else None,
                    )
                    for index, day in enumerate(days)
                ],
            )
    return repository_database, prices, market


def test_router_recognizes_stock_administrator_question() -> None:
    prediction = route_question({
        "user_question": "沐邦的重整管理人是哪家律所，历史表现如何？",
        "object": {"kind": "stock", "ref": "603398"},
    })

    assert prediction.predicted_route == "answer_query"
    assert prediction.matched_rules == ["stock_administrator_history_query"]


def test_answer_card_separates_fact_case_window_and_small_sample(tmp_path) -> None:
    repository, prices, market = _sources(tmp_path)

    card = card_stock_administrator_history(
        "603398",
        "沐邦的重整管理人是谁，历史表现如何？",
        repository_database=repository,
        price_database=prices,
        market_database=market,
    )
    card.validate()

    row_types = {row["记录类型"] for row in card.body_rows}
    assert {
        "管理人任职事实",
        "管理人节点案例",
        "管理人样本门槛",
    } <= row_types
    assert "管理人节点分布" not in row_types
    fact = next(row for row in card.body_rows if row["记录类型"] == "管理人任职事实")
    assert fact["管理人"] == "北京市金杜（深圳）律师事务所"
    case = next(row for row in card.body_rows if row["记录类型"] == "管理人节点案例")
    assert case["后20日相对ST(百分点)"] != "基准缺数据"
    assert case["后20日相对中证2000(百分点)"] != "基准缺数据"
    assert any("少于 8 个案件" in caveat for caveat in card.caveats)


def test_orchestrator_builds_specialized_human_narrative(tmp_path, monkeypatch) -> None:
    repository, prices, market = _sources(tmp_path)
    card = card_stock_administrator_history(
        "603398",
        "沐邦的重整管理人是哪家律所，历史表现如何？",
        repository_database=repository,
        price_database=prices,
        market_database=market,
    )
    monkeypatch.setattr(
        orchestrator_module,
        "card_stock_administrator_history",
        lambda symbol, question: card,
    )

    response = api_orchestrate(ResearchRequest.model_validate({
        "question": "沐邦的重整管理人是哪家律所，历史表现如何？",
        "object": {"kind": "stock", "ref": "603398"},
        "llm_mode": "off",
    }))

    assert response.route.matched_rules == ["stock_administrator_history_query"]
    assert response.answer_card is not None
    assert response.narrative is not None
    assert "北京市金杜（深圳）律师事务所" in response.narrative.direct_answer.text
    assert "不生成成功率、分布结论或排名" in response.narrative.direct_answer.text
