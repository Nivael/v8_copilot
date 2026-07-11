from stock_resolver import normalize_stock_name, resolve_stock


def test_resolves_current_and_historical_st_names_from_v5_metadata() -> None:
    current = resolve_stock("华微电子最近有哪些风险节点？")
    historical = resolve_stock("ST华微为什么被ST？")

    assert current is not None and current.symbol == "600360"
    assert historical is not None and historical.symbol == "600360"
    assert historical.matched_alias == "华微"


def test_symbol_input_remains_canonical() -> None:
    resolution = resolve_stock("请分析 603398 最近公告")

    assert resolution is not None
    assert resolution.symbol == "603398"


def test_status_prefix_and_company_suffix_are_not_identity() -> None:
    assert normalize_stock_name("*ST 华微") == "华微"
    assert normalize_stock_name("吉林华微电子股份有限公司") == "吉林华微电子"


def test_unresolved_name_returns_none_instead_of_guessing() -> None:
    assert resolve_stock("ST不存在为什么被ST？") is None
