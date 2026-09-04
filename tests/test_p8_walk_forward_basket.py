from p8_walk_forward_basket import _period_performance, simulate_year


def test_basket_delays_one_price_buy_and_keeps_locked_sell() -> None:
    calendar = [
        "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06",
        "2023-01-09", "2023-01-10", "2023-01-11", "2023-01-12", "2023-01-13",
        "2023-01-16", "2023-01-17", "2023-01-18", "2023-01-19", "2023-01-20",
    ]
    funnel = [
        {
            "decision_date": "2023-01-06", "test_year": 2023,
            "symbol": "000001", "primary_lane": "persistent_activity",
        },
        {
            "decision_date": "2023-01-13", "test_year": 2023,
            "symbol": "000002", "primary_lane": "event_frontier",
        },
    ]
    prices = {
        "000001": {day: 10.0 for day in calendar},
        "000002": {day: 10.0 for day in calendar},
    }
    states = {(symbol, day): {"known": True, "buy": True, "sell": True} for symbol in prices for day in calendar}
    states[("000001", "2023-01-09")]["buy"] = False
    states[("000001", "2023-01-16")]["sell"] = False
    benchmark = {day: 100.0 for day in calendar}
    result = simulate_year(
        year=2023, calendar=calendar, funnel=funnel, prices=prices,
        trade_states=states, benchmark=benchmark, delisting_dates={}, cost=0.005,
    )
    trades = result["trade_ledger"]
    first_buy = next(item for item in trades if item["side"] == "buy")
    assert first_buy["symbol"] == "000001"
    assert first_buy["trade_date"] == "2023-01-10"
    first_sell = next(item for item in trades if item["side"] == "sell" and item["symbol"] == "000001")
    assert first_sell["trade_date"] == "2023-01-17"
    assert result["locked_sell_days"] == 1
    assert result["portfolio_return"] < 0  # only transaction costs in flat prices


def test_basket_never_assumes_unknown_tradeability() -> None:
    calendar = ["2023-01-02", "2023-01-03"]
    funnel = [{
        "decision_date": "2023-01-02", "test_year": 2023,
        "symbol": "000001", "primary_lane": "persistent_activity",
    }]
    result = simulate_year(
        year=2023, calendar=calendar, funnel=funnel,
        prices={"000001": {day: 10.0 for day in calendar}},
        trade_states={}, benchmark={day: 100.0 for day in calendar},
        delisting_dates={}, cost=0.005,
    )
    assert result["trade_count"] == 0
    assert result["unknown_trade_state_attempts"] == 1
    assert result["portfolio_return"] == 0


def test_period_performance_is_a_non_decision_diagnostic() -> None:
    result = _period_performance(
        {"nav_by_day": {"2024-04-30": 1.0, "2024-05-06": 1.1}},
        {"2024-04-30": 100.0, "2024-05-06": 105.0},
        start="2024-04-30", through="2024-10-29",
    )
    assert result["status"] == "observable"
    assert abs(result["excess_return_st"] - .05) < 1e-12


def test_basket_reports_total_loss_and_last_observable_terminal_conventions() -> None:
    calendar = ["2023-01-02", "2023-01-03", "2023-01-04"]
    funnel = [{
        "decision_date": "2023-01-02", "test_year": 2023,
        "symbol": "000001", "primary_lane": "persistent_activity",
    }]
    states = {("000001", "2023-01-03"): {"known": True, "buy": True, "sell": True}}
    common = dict(
        year=2023, calendar=calendar, funnel=funnel,
        prices={"000001": {"2023-01-03": 10.0}}, trade_states=states,
        benchmark={day: 100.0 for day in calendar},
        delisting_dates={"000001": "2023-01-04"}, cost=0.0,
    )
    lower = simulate_year(**common)
    upper = simulate_year(**common, delist_total_loss=False)
    assert lower["portfolio_return"] == -1.0
    assert upper["portfolio_return"] == 0.0
    assert lower["delist_terminal_convention"] == "total_loss"
    assert upper["delist_terminal_convention"] == "last_observable_value"
