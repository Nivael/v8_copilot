from stock_resolver import normalize_stock_name, resolve_stock, resolve_stocks


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


def test_central_huijin_is_not_a_listed_stock_alias() -> None:
    for question in ["中央汇金的ETF持仓", "中央 汇金投资有限责任公司的公开增持", "中央汇金资产管理有限责任公司"]:
        assert resolve_stock(question) is None
        assert resolve_stocks(question) == []


def test_institution_mask_preserves_an_explicit_stock_elsewhere_or_by_code() -> None:
    named = resolve_stock("中央汇金与汇金股份不是同一主体")
    assert named is not None and named.symbol == "300368"
    assert [row.symbol for row in resolve_stocks("中央汇金与汇金股份不是同一主体")] == ["300368"]
    assert resolve_stock("中央汇金的持仓；另查300368").symbol == "300368"
