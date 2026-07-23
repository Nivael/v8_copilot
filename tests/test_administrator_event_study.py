import sqlite3
from datetime import date, timedelta

from administrator_event_study import (
    cohort_distribution_rows,
    organization_event_studies,
    study_administrator_event,
)
from restructuring_administrators import (
    AdministratorRepository,
    AnnouncementSourceRow,
    extract_administrator_appointment,
)


def _trading_days(start: date, count: int) -> list[str]:
    values: list[str] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def _databases(tmp_path):
    prices = tmp_path / "prices.sqlite3"
    market = tmp_path / "market.sqlite3"
    days = _trading_days(date(2025, 1, 1), 100)
    with sqlite3.connect(prices) as connection:
        connection.execute(
            "create table daily_prices ("
            "symbol text,trade_date text,adjust text,close real)"
        )
        connection.executemany(
            "insert into daily_prices values (?,?,?,?)",
            [
                ("603398", day, "qfq", 10 + index * 0.1)
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
    return prices, market, days


def _event(information_date: str) -> dict[str, str]:
    return {
        "event_id": "E1",
        "case_id": "C1",
        "assignment_id": "A1",
        "symbol": "603398",
        "appointment_kind": "temporary_administrator",
        "event_type": "administrator_appointed",
        "canonical_name": "北京市金杜（深圳）律师事务所",
        "information_available_date": information_date,
    }


def test_date_only_event_uses_first_strictly_later_session(tmp_path) -> None:
    prices, market, days = _databases(tmp_path)
    information_date = days[25]

    study = study_administrator_event(
        event=_event(information_date),
        organization_id="ORG1",
        price_database=prices,
        market_database=market,
    )

    assert study.baseline_date == days[25]
    assert study.t0_date == days[26]
    assert study.windows["post5"].end_date == days[30]
    assert study.windows["post20"].end_date == days[45]
    assert study.windows["post20"].relative_returns_pp["csi_2000"] is not None


def test_missing_benchmark_is_explicit_and_never_interpolated(tmp_path) -> None:
    prices, market, days = _databases(tmp_path)
    with sqlite3.connect(market) as connection:
        connection.execute(
            "delete from benchmark_daily where benchmark_id='csi_2000' and trade_date=?",
            (days[45],),
        )

    study = study_administrator_event(
        event=_event(days[25]),
        organization_id="ORG1",
        price_database=prices,
        market_database=market,
    )

    metric = study.windows["post20"]
    assert "csi_2000" not in metric.benchmark_returns_pct
    assert any("csi_2000 缺事件共同交易日，不插值" in gap for gap in metric.gaps)


def test_same_case_and_appointment_kind_is_deduplicated(tmp_path) -> None:
    prices, market, _ = _databases(tmp_path)
    repository = AdministratorRepository(tmp_path / "administrators.sqlite3")
    base_body = (
        "江西沐邦高科股份有限公司关于预重整事项的公告。"
        "2025年1月20日，法院作出（2025）赣01破申19号决定书，"
        "指定北京市金杜（深圳）律师事务所担任临时管理人。"
        "公司能否进入重整程序存在重大不确定性，敬请注意风险。"
    ) * 3
    for announcement_id, published in (("A1", "2025-01-20"), ("A2", "2025-01-21")):
        result = extract_administrator_appointment(AnnouncementSourceRow(
            announcement_id=announcement_id,
            symbol="603398",
            announcement_date=date.fromisoformat(published),
            title="关于法院指定临时管理人的公告",
            body_text=base_body,
            source="cninfo",
        ))
        repository.persist(result)
    organization_id = result.organizations[0].organization_id

    studies = organization_event_studies(
        repository=repository,
        organization_id=organization_id,
        price_database=prices,
        market_database=market,
    )

    assert len(studies) == 1


def test_small_cohort_does_not_emit_distribution() -> None:
    assert cohort_distribution_rows([], minimum_cases=8) == []
