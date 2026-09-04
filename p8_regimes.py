"""Frozen exit-pricing regime registry for P8 reference stratification."""
from __future__ import annotations

from dataclasses import dataclass


REGISTRY_VERSION = "p8_exit_pricing_regimes_v1"


@dataclass(frozen=True)
class Regime:
    regime_version: str
    start_date: str
    end_date: str
    official_sources: tuple[str, ...]
    note: str


REGIMES: tuple[Regime, ...] = (
    Regime(
        regime_version="pre_2020_exit_rules",
        start_date="1900-01-01",
        end_date="2020-12-30",
        official_sources=(),
        note="2020-12-31 沪深退市新规实施前；仅作旧制度分层，不与之后样本混合。",
    ),
    Regime(
        regime_version="2020_exit_reform",
        start_date="2020-12-31",
        end_date="2024-04-29",
        official_sources=(
            "https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20201231_5294528.shtml",
            "https://www.szse.cn/www/aboutus/trends/news/t20201231_584060.html",
        ),
        note="沪深 2020 退市新规自 2020-12-31 发布实施。",
    ),
    Regime(
        regime_version="2024_exit_reform",
        start_date="2024-04-30",
        end_date="9999-12-31",
        official_sources=(
            "https://www.szse.cn/lawrules/rule/repeal/rules/t20240430_607069.html",
            "https://www.bse.cn/cxjg_list/200021755.html",
            "https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/mainipo/c/c_20260424_10816589.shtml",
        ),
        note=(
            "2024-04-30 退市规则修订后的退出定价制度；上交所 2026 修订明确风险警示、"
            "终止上市仍沿用 2024 通知的衔接安排，因此不另切退出定价 regime。"
        ),
    ),
)


def regime_for_date(value: str) -> Regime:
    day = str(value)[:10]
    for regime in REGIMES:
        if regime.start_date <= day <= regime.end_date:
            return regime
    raise ValueError(f"日期不在 regime registry: {value!r}")


def registry_payload() -> dict[str, object]:
    return {
        "registry_version": REGISTRY_VERSION,
        "regimes": [
            {
                "regime_version": item.regime_version,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "official_sources": list(item.official_sources),
                "note": item.note,
            }
            for item in REGIMES
        ],
    }
