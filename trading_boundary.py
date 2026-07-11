"""Shared deterministic boundary detection for trading-advice requests."""
from __future__ import annotations

import re


_DIRECT_TERMS = (
    "目标价", "仓位", "买入", "卖出", "加仓", "减仓", "抄底", "割肉",
    "满仓", "交易信号", "埋伏", "上车", "买点", "卖点", "止损", "止盈",
    "继续持有", "持有还是", "该不该买", "要不要买", "能不能买", "是否能买",
    "值不值得买", "适不适合买", "该买", "该卖", "会涨停", "推荐买",
    "最值得买",
)

_SEPARATED_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"(?:能|可以|可不可以|是否可以|适合).{0,20}(?:买|买入|卖|卖出|持有|加仓|减仓)(?:.{0,4}[吗么]|[?？]$)",
    r"(?:买|买入|卖|卖出|持有|加仓|减仓).{0,20}(?:可以|合适|适合)(?:.{0,4}[吗么]|[?？]$)",
    r"(?:推荐|挑|选).{0,20}(?:股票|个股|st|买)",
))


def normalize_question(text: str) -> str:
    return "".join(text.lower().split())


def is_trading_advice_request(text: str) -> bool:
    """Return True for action/position/price requests, including split phrasing.

    Chinese questions often place a stock name between the action and the final
    particle, for example ``能买沐邦吗``. A contiguous keyword list cannot catch
    that shape, so the shared detector combines explicit terms with bounded
    patterns. It deliberately does not inspect research data or infer intent from
    a stock's price movement.
    """
    normalized = normalize_question(text)
    return any(term in normalized for term in _DIRECT_TERMS) or any(
        pattern.search(normalized) for pattern in _SEPARATED_PATTERNS
    )
