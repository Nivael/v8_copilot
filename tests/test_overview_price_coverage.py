import sqlite3

import pytest

import answer_engine
from api_contract import ResearchObject, ResearchRequest
from evidence_gateway import build_evidence_pack
from lens_binding import LensGap
from market_comparison import MarketComparisonWindow


@pytest.fixture
def price_sources(tmp_path, monkeypatch):
    database = tmp_path / "prices.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("create table daily_prices(symbol,trade_date,close,turnover_rate,adjust)")
        # Another company's newer prices must never date the requested stock.
        connection.execute("insert into daily_prices values ('000001','2026-09-09',99,1,'qfq')")
    monkeypatch.setattr(answer_engine, "BASE_DB", database)

    def status(symbol):
        return answer_engine.AnswerCard(
            question="测试状态", object_ref=f"stock:{symbol}", view="query",
            as_of="2026-06-01", data_snapshot_as_of="2026-06-01",
            sample_scope="合成测试", evidence_grade="descriptive_query",
            source_freshness={"st_status_fetched_at": "2026-06-01"},
            body_rows=[{"row_id": "status", "记录类型": "状态区间", "开始日": "2026-06-01"}],
            lens_gap=[LensGap(gap_id="synthetic_status", missing_for="测试状态",
                              sediment_as="question_card:synthetic_status")],
            caveats=list(answer_engine.FIXED_CAVEATS), provenance=["synthetic:status"],
        )

    monkeypatch.setattr(answer_engine, "card_st_status_timeline", status)
    monkeypatch.setattr(answer_engine, "load_market_comparison", lambda **kwargs:
        MarketComparisonWindow(status="unavailable", symbol=kwargs["symbol"], sessions=10,
                               gaps=["合成测试没有同窗比较行情"]))
    return database


@pytest.mark.parametrize("raw_price_only", [False, True])
def test_missing_qfq_price_returns_gap_without_borrowing_a_price_date(price_sources, raw_price_only):
    if raw_price_only:
        with sqlite3.connect(price_sources) as connection:
            connection.execute("insert into daily_prices values ('603398','2026-09-08',88,2,'raw')")

    pack = build_evidence_pack(ResearchRequest(
        question="沐邦最近股价和换手率怎样？",
        object=ResearchObject(kind="stock", ref="603398"), llm_mode="off",
    ))

    assert any(gap.get("gap_id") == "stock_price_coverage" for gap in pack.coverage_gaps)
    assert "price_data_as_of" not in pack.source_freshness
    assert not any(row.get("row_id") == "recent_price_window" for row in pack.rows)
    assert pack.question_scope["as_of"] == "2026-06-01"
    assert any(row.get("row_id") == "market_comparison_gap" for row in pack.rows)


def test_comprehensive_overview_keeps_missing_price_boundary_explicit(price_sources):
    card = answer_engine.card_stock_research_overview(
        "603398", "分析一下最近股价和换手率", dimensions=("price",),
    )

    card.validate()
    boundary = next(row for row in card.body_rows
                    if row.get("row_id") == "analysis_freshness_boundary")
    assert boundary["价格截至"] == ""
    assert boundary["价格覆盖ST后"] is False
    assert "price_data_as_of" not in card.source_freshness
    assert any(gap.gap_id == "stock_price_coverage" for gap in card.lens_gap)


def test_overview_price_date_comes_from_the_requested_stock_qfq_rows(price_sources):
    with sqlite3.connect(price_sources) as connection:
        connection.executemany("insert into daily_prices values (?,?,?,?,?)", [
            ("603398", f"2026-08-{day:02d}", 10 + day / 10, 2, "qfq")
            for day in range(1, 13)
        ])
        connection.execute("insert into daily_prices values ('603398','2026-09-08',88,2,'raw')")

    card = answer_engine.card_stock_research_overview(
        "603398", "最近股价和换手率怎样？", dimensions=("price",),
    )

    card.validate()
    assert card.as_of == card.data_snapshot_as_of == "2026-08-12"
    assert card.source_freshness["price_data_as_of"] == "2026-08-12"
    price = next(row for row in card.body_rows if row.get("row_id") == "recent_price_window")
    assert price["截至"] == "2026-08-12"
    assert price["最新收盘"] == 11.2
    assert not any(gap.gap_id == "stock_price_coverage" for gap in card.lens_gap)
