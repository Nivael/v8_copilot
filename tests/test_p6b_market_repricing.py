from __future__ import annotations

import json
import sqlite3

from market_factors import MarketCapPoint, MarketFactorRepository
from p6b_market_repricing import (
    build_p6b_market_answer_card,
    build_p6b_market_map,
    episode_relative_repricing,
    market_cap_change_decomposition,
)


ANCHOR = "2024-01-02"
START = "2024-01-03"
END = "2024-01-04"


def _market_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table benchmark_daily (
                benchmark_id text,
                trade_date text,
                close real,
                coverage_ratio real
            );
            create table st_membership_daily (
                trade_date text,
                symbol text
            );
            insert into benchmark_daily values
                ('st_equal_weight_v1','2024-01-02',1000,1),
                ('st_equal_weight_v1','2024-01-03',1020,1),
                ('st_equal_weight_v1','2024-01-04',1030.2,1),
                ('csi_all_share','2024-01-02',100,1),
                ('csi_all_share','2024-01-03',101,1),
                ('csi_all_share','2024-01-04',102,1),
                ('csi_2000','2024-01-02',200,1),
                ('csi_2000','2024-01-03',202,1),
                ('csi_2000','2024-01-04',198,1);
            insert into st_membership_daily values
                ('2024-01-03','000001'),
                ('2024-01-03','000002'),
                ('2024-01-03','000003'),
                ('2024-01-04','000001'),
                ('2024-01-04','000002'),
                ('2024-01-04','000003');
        """)


def _price_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            create table daily_prices (
                symbol text,
                trade_date text,
                adjust text,
                close real,
                pct_change real
            );
            insert into daily_prices values
                ('000001','2024-01-02','qfq',10,null),
                ('000001','2024-01-03','qfq',10.5,5),
                ('000001','2024-01-04','qfq',11,4.76190476),
                ('000002','2024-01-03','qfq',10,1),
                ('000003','2024-01-03','qfq',10,3),
                ('000002','2024-01-04','qfq',10,0),
                ('000003','2024-01-04','qfq',10,2);
        """)


def _factor_database(path, *, end_shares: float = 100) -> None:
    repository = MarketFactorRepository(path)
    for day, target_cap, target_shares in [
        (ANCHOR, 1_000, 100),
        (START, 1_000, 100),
        (END, 1_100, end_shares),
    ]:
        repository.store_snapshot(
            trade_date=day,
            membership_symbols=["000001", "000002", "000003"],
            points=[
                MarketCapPoint(
                    symbol="000001", trade_date=day,
                    total_market_value=target_cap,
                    total_shares=target_shares,
                ),
                MarketCapPoint(
                    symbol="000002", trade_date=day,
                    total_market_value=2_000, total_shares=100,
                ),
                MarketCapPoint(
                    symbol="000003", trade_date=day,
                    total_market_value=3_000, total_shares=100,
                ),
            ],
        )


def test_episode_repricing_uses_ex_target_daily_membership_benchmark(
    tmp_path,
) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    _market_database(market)
    _price_database(prices)
    _factor_database(factors)

    result = episode_relative_repricing(
        market_context_database=market,
        market_factor_database=factors,
        price_database=prices,
        symbol="000001",
        episode_start_date=START,
        valuation_date=END,
        minimum_valid_benchmark_members=2,
    )

    assert result.status == "ready"
    assert result.anchor_date == ANCHOR
    assert result.end_date == END
    assert result.trading_day_count == 2
    assert result.target_qfq_return == 0.1
    assert result.st_equal_weight_ex_target_return == 0.0302
    assert result.episode_relative_repricing == round(1.1 / 1.0302 - 1, 10)
    assert result.minimum_daily_benchmark_coverage == 1
    assert result.capital_structure.status == "clear"
    assert [item.status for item in result.market_context] == ["ready", "ready"]


def test_capital_structure_change_blocks_exact_repricing_but_keeps_decomposition(
    tmp_path,
) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    _market_database(market)
    _price_database(prices)
    _factor_database(factors, end_shares=200)

    repricing = episode_relative_repricing(
        market_context_database=market,
        market_factor_database=factors,
        price_database=prices,
        symbol="000001",
        episode_start_date=START,
        valuation_date=END,
        minimum_valid_benchmark_members=2,
    )
    decomposition = market_cap_change_decomposition(
        market_factor_database=factors,
        symbol="000001",
        start_date=ANCHOR,
        end_date=END,
    )

    assert repricing.status == "unavailable"
    assert repricing.gap_codes == ["capital_structure_contaminated"]
    assert repricing.episode_relative_repricing is None
    assert repricing.capital_structure.status == "changed"
    assert decomposition.status == "ready"
    assert decomposition.total_market_value_change == 0.1
    assert decomposition.share_count_effect == 1
    assert decomposition.price_effect == -0.45
    assert round(
        decomposition.price_effect
        + decomposition.share_count_effect
        + decomposition.interaction_effect,
        10,
    ) == decomposition.total_market_value_change


def test_prehistory_episode_returns_gap_instead_of_substitute(tmp_path) -> None:
    result = episode_relative_repricing(
        market_context_database=tmp_path / "market.sqlite3",
        market_factor_database=tmp_path / "factors.sqlite3",
        price_database=tmp_path / "prices.sqlite3",
        symbol="000001",
        episode_start_date="2021-03-17",
        valuation_date="2021-04-01",
    )

    assert result.status == "unavailable"
    assert result.gap_codes == ["st_equal_weight_history_unavailable"]


def test_answer_card_is_descriptive_only_and_keeps_gaps_visible(tmp_path) -> None:
    market = tmp_path / "market.sqlite3"
    prices = tmp_path / "prices.sqlite3"
    factors = tmp_path / "factors.sqlite3"
    _market_database(market)
    _price_database(prices)
    _factor_database(factors)

    result = build_p6b_market_map(
        symbol="000001",
        episode_start_date=START,
        valuation_date=END,
        market_factor_database=factors,
        market_context_database=market,
        price_database=prices,
    )
    card = build_p6b_market_answer_card(result)
    payload = card.to_dict()
    blob = json.dumps(payload, ensure_ascii=False)

    assert payload["contract_version"] == "v8_answer_contract_v0"
    assert payload["body_rows"][0]["validation_state"] == "descriptive_only"
    assert payload["lens_gap"][0]["gap_id"] == "LG-P6B-MARKET-MAP"
    assert "意味着便宜" not in blob
    assert "底部" not in blob
    assert all(
        term not in claim["text"]
        for claim in payload["analysis_claims"]
        for term in ("低估", "便宜", "底部", "交易信号")
    )
