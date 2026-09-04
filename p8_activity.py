"""P8 cumulative activity features with outcome-blind frozen profiles."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from market_activity import MarketActivityFact


CONTRACT_VERSION = "p8_cumulative_activity_v2"
MIN_BASELINE = 60
MAX_BASELINE = 120
FEATURE_WINDOW = 20


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class P8ActivityFeature(StrictModel):
    feature_id: str = Field(pattern=r"^P8AF-[A-F0-9]{20}$")
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    symbol: str = Field(pattern=r"^\d{6}$")
    trade_date: str
    baseline_observations: int = Field(ge=0)
    window_observations: int = Field(ge=0)
    cum_turnover_log_excess_10: float | None = None
    cum_turnover_log_excess_20: float | None = None
    elevated_day_ratio_20: float | None = None
    range_compression_20: float | None = None
    price_drift_20: float | None = None
    excess_return_st_20: float | None = None
    excess_return_csi2000_20: float | None = None
    amount_weighted_log_price_slope_20: float | None = None
    single_day_qfq_return: float | None = None
    single_day_excess_return_st: float | None = None
    single_day_amplitude_ratio: float | None = None
    st_turnover_median: float | None = None
    st_turnover_regime_change_20: float | None = None
    calculable: bool
    data_gaps: list[str] = Field(default_factory=list)


class ShapeThresholds(StrictModel):
    profile: Literal["broad", "base", "strict"]
    cum_log_excess_20_min: float
    elevated_day_ratio_min: float
    stable_abs_excess_return_max: float
    range_compression_max: float
    down_excess_return_max: float
    single_day_excess_return_min: float
    single_day_amplitude_ratio_min: float


class ShapeLabel(StrictModel):
    feature_id: str
    profile: Literal["broad", "base", "strict"]
    label: Literal[
        "persistent_activity_price_stable",
        "single_day_activity_price_jump",
        "persistent_activity_price_down",
        "quiet",
        "unknown",
    ]
    reasons: list[str]


FROZEN_SHAPE_PROFILES: tuple[ShapeThresholds, ...] = (
    ShapeThresholds(
        profile="broad", cum_log_excess_20_min=2.0,
        elevated_day_ratio_min=0.40, stable_abs_excess_return_max=0.10,
        range_compression_max=1.10, down_excess_return_max=-0.10,
        single_day_excess_return_min=0.03, single_day_amplitude_ratio_min=1.20,
    ),
    ShapeThresholds(
        profile="base", cum_log_excess_20_min=3.0,
        elevated_day_ratio_min=0.50, stable_abs_excess_return_max=0.08,
        range_compression_max=1.00, down_excess_return_max=-0.08,
        single_day_excess_return_min=0.05, single_day_amplitude_ratio_min=1.50,
    ),
    ShapeThresholds(
        profile="strict", cum_log_excess_20_min=4.0,
        elevated_day_ratio_min=0.60, stable_abs_excess_return_max=0.06,
        range_compression_max=0.90, down_excess_return_max=-0.06,
        single_day_excess_return_min=0.08, single_day_amplitude_ratio_min=2.00,
    ),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _return(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1


def _weighted_slope(prices: list[float], amounts: list[float]) -> float | None:
    if len(prices) != len(amounts) or len(prices) < 2:
        return None
    if any(value <= 0 or not math.isfinite(value) for value in prices):
        return None
    clean_weights = [value if value > 0 and math.isfinite(value) else 0.0 for value in amounts]
    total = sum(clean_weights)
    if total <= 0:
        return None
    xs = list(range(len(prices)))
    ys = [math.log(value) for value in prices]
    x_bar = sum(weight * x for weight, x in zip(clean_weights, xs)) / total
    y_bar = sum(weight * y for weight, y in zip(clean_weights, ys)) / total
    denominator = sum(weight * (x - x_bar) ** 2 for weight, x in zip(clean_weights, xs))
    if denominator <= 0:
        return None
    return sum(
        weight * (x - x_bar) * (y - y_bar)
        for weight, x, y in zip(clean_weights, xs, ys)
    ) / denominator


def _rank_percentile(history: list[float], current: float) -> float | None:
    if not history:
        return None
    less = sum(value < current for value in history)
    equal = sum(value == current for value in history)
    return (less + 0.5 * equal) / len(history)


@dataclass(frozen=True)
class _Prepared:
    fact: MarketActivityFact
    qfq_close: float | None
    lagged_turnover_median: float | None = None
    lagged_turnover_percentile: float | None = None


def build_activity_features(
    facts: list[MarketActivityFact], *,
    qfq_close_by_symbol_date: dict[tuple[str, str], float] | None = None,
    benchmark_close_by_id_date: dict[tuple[str, str], float] | None = None,
) -> list[P8ActivityFeature]:
    """Build point-in-time features. No outcome, announcement, or P8A input is accepted."""

    qfq = qfq_close_by_symbol_date or {}
    benchmarks = benchmark_close_by_id_date or {}
    by_symbol: dict[str, list[MarketActivityFact]] = defaultdict(list)
    by_date_turnover: dict[str, list[float]] = defaultdict(list)
    for fact in facts:
        by_symbol[fact.symbol].append(fact)
        if fact.eligible_for_anomaly and fact.turnover_rate_f is not None and fact.turnover_rate_f > 0:
            by_date_turnover[fact.trade_date].append(fact.turnover_rate_f)
    daily_st_median = {
        day: statistics.median(values) for day, values in by_date_turnover.items() if values
    }
    sorted_st_days = sorted(daily_st_median)
    st_day_index = {day: index for index, day in enumerate(sorted_st_days)}

    output: list[P8ActivityFeature] = []
    for symbol, symbol_facts in sorted(by_symbol.items()):
        ordered = sorted(symbol_facts, key=lambda item: item.trade_date)
        prepared: list[_Prepared] = []
        eligible_turnover: list[float] = []
        for fact in ordered:
            history = eligible_turnover[-MAX_BASELINE:]
            median = _median(history) if len(history) >= MIN_BASELINE else None
            percentile = (
                _rank_percentile(history, fact.turnover_rate_f)
                if median is not None and fact.turnover_rate_f is not None and fact.turnover_rate_f > 0
                else None
            )
            prepared.append(_Prepared(
                fact=fact,
                qfq_close=qfq.get((symbol, fact.trade_date), fact.close),
                lagged_turnover_median=median,
                lagged_turnover_percentile=percentile,
            ))
            if fact.eligible_for_anomaly and fact.turnover_rate_f is not None and fact.turnover_rate_f > 0:
                eligible_turnover.append(fact.turnover_rate_f)

        for index, current in enumerate(prepared):
            gaps: list[str] = []
            previous = [
                item for item in prepared[:index]
                if item.fact.eligible_for_anomaly
                and item.fact.turnover_rate_f is not None
                and item.fact.turnover_rate_f > 0
            ]
            baseline_observations = min(len(previous), MAX_BASELINE)
            window = [
                item for item in prepared[: index + 1]
                if item.fact.eligible_for_anomaly
                and item.fact.turnover_rate_f is not None
                and item.fact.turnover_rate_f > 0
            ][-FEATURE_WINDOW:]
            if baseline_observations < MIN_BASELINE:
                gaps.append("insufficient_lagged_turnover_baseline")
            if len(window) < FEATURE_WINDOW:
                gaps.append("insufficient_feature_window")

            log_excess: list[float] = []
            elevated: list[bool] = []
            for item in window:
                median = item.lagged_turnover_median
                value = item.fact.turnover_rate_f
                if median is None or median <= 0 or value is None or value <= 0:
                    log_excess = []
                    elevated = []
                    break
                log_excess.append(math.log(value / median))
                percentile = item.lagged_turnover_percentile
                if percentile is None:
                    elevated = []
                    break
                elevated.append(percentile >= 0.75)
            cum10 = sum(log_excess[-10:]) if len(log_excess) == FEATURE_WINDOW else None
            cum20 = sum(log_excess) if len(log_excess) == FEATURE_WINDOW else None
            elevated_ratio = (
                sum(elevated) / FEATURE_WINDOW if len(elevated) == FEATURE_WINDOW else None
            )
            if cum20 is None:
                gaps.append("turnover_log_excess_unavailable")

            baseline_for_amplitude = [
                item.fact.amplitude_pct for item in prepared[: max(0, index - FEATURE_WINDOW + 1)]
                if item.fact.eligible_for_anomaly and item.fact.amplitude_pct is not None
            ][-MAX_BASELINE:]
            window_amplitude = [
                item.fact.amplitude_pct for item in window if item.fact.amplitude_pct is not None
            ]
            amplitude_base = _median(baseline_for_amplitude) if len(baseline_for_amplitude) >= MIN_BASELINE else None
            range_compression = (
                statistics.median(window_amplitude) / amplitude_base
                if len(window_amplitude) == FEATURE_WINDOW and amplitude_base is not None and amplitude_base > 0
                else None
            )
            if range_compression is None:
                gaps.append("range_compression_unavailable")
            current_amplitude = current.fact.amplitude_pct
            single_day_amplitude_ratio = (
                current_amplitude / amplitude_base
                if current_amplitude is not None and amplitude_base is not None and amplitude_base > 0
                else None
            )

            prices = [item.qfq_close for item in window]
            valid_prices = [float(value) for value in prices if value is not None and value > 0]
            price_drift = (
                _return(valid_prices[0], valid_prices[-1])
                if len(valid_prices) == FEATURE_WINDOW else None
            )
            amounts = [item.fact.amount for item in window]
            valid_amounts = [float(value) for value in amounts if value is not None]
            slope = (
                _weighted_slope(valid_prices, valid_amounts)
                if len(valid_prices) == FEATURE_WINDOW and len(valid_amounts) == FEATURE_WINDOW else None
            )
            if price_drift is None:
                gaps.append("qfq_price_window_unavailable")
            if slope is None:
                gaps.append("amount_weighted_slope_unavailable")

            prior_observation = next((
                item for item in reversed(prepared[:index])
                if item.qfq_close is not None and item.qfq_close > 0
            ), None)
            prior_qfq = prior_observation.qfq_close if prior_observation else None
            single_day_qfq_return = _return(prior_qfq, current.qfq_close)

            start_day = window[0].fact.trade_date if len(window) == FEATURE_WINDOW else ""
            st_return = _return(
                benchmarks.get(("st_equal_weight_v1", start_day)),
                benchmarks.get(("st_equal_weight_v1", current.fact.trade_date)),
            ) if start_day else None
            csi_return = _return(
                benchmarks.get(("csi_2000", start_day)),
                benchmarks.get(("csi_2000", current.fact.trade_date)),
            ) if start_day else None
            st_excess = price_drift - st_return if price_drift is not None and st_return is not None else None
            csi_excess = price_drift - csi_return if price_drift is not None and csi_return is not None else None
            prior_day = prior_observation.fact.trade_date if prior_observation else ""
            st_single_return = _return(
                benchmarks.get(("st_equal_weight_v1", prior_day)),
                benchmarks.get(("st_equal_weight_v1", current.fact.trade_date)),
            ) if prior_day else None
            single_day_excess_st = (
                single_day_qfq_return - st_single_return
                if single_day_qfq_return is not None and st_single_return is not None else None
            )

            st_median = daily_st_median.get(current.fact.trade_date)
            regime_change = None
            st_index = st_day_index.get(current.fact.trade_date)
            if st_median is not None and st_index is not None and st_index >= FEATURE_WINDOW - 1:
                start_median = daily_st_median.get(sorted_st_days[st_index - FEATURE_WINDOW + 1])
                if start_median is not None and start_median > 0:
                    regime_change = st_median / start_median - 1

            calculable = all(value is not None for value in (
                cum10, cum20, elevated_ratio, range_compression,
                price_drift, slope, st_median,
            ))
            payload = {
                "symbol": symbol,
                "trade_date": current.fact.trade_date,
                "cum20": cum20,
                "elevated": elevated_ratio,
                "range": range_compression,
                "drift": price_drift,
                "st_excess": st_excess,
                "csi_excess": csi_excess,
                "slope": slope,
                "single_day_qfq_return": single_day_qfq_return,
                "single_day_excess_st": single_day_excess_st,
                "single_day_amplitude_ratio": single_day_amplitude_ratio,
                "st_regime": regime_change,
            }
            output.append(P8ActivityFeature(
                feature_id=f"P8AF-{_digest(payload)[:20].upper()}",
                symbol=symbol,
                trade_date=current.fact.trade_date,
                baseline_observations=baseline_observations,
                window_observations=len(window),
                cum_turnover_log_excess_10=cum10,
                cum_turnover_log_excess_20=cum20,
                elevated_day_ratio_20=elevated_ratio,
                range_compression_20=range_compression,
                price_drift_20=price_drift,
                excess_return_st_20=st_excess,
                excess_return_csi2000_20=csi_excess,
                amount_weighted_log_price_slope_20=slope,
                single_day_qfq_return=single_day_qfq_return,
                single_day_excess_return_st=single_day_excess_st,
                single_day_amplitude_ratio=single_day_amplitude_ratio,
                st_turnover_median=st_median,
                st_turnover_regime_change_20=regime_change,
                calculable=calculable,
                data_gaps=sorted(set(gaps)),
            ))
    return sorted(output, key=lambda item: (item.trade_date, item.symbol))


def classify_shape(
    feature: P8ActivityFeature, thresholds: ShapeThresholds,
    *, single_day_strict: bool = False,
) -> ShapeLabel:
    if not feature.calculable:
        return ShapeLabel(
            feature_id=feature.feature_id, profile=thresholds.profile,
            label="unknown", reasons=feature.data_gaps or ["feature_not_calculable"],
        )
    persistent = bool(
        feature.cum_turnover_log_excess_20 is not None
        and feature.cum_turnover_log_excess_20 >= thresholds.cum_log_excess_20_min
        and feature.elevated_day_ratio_20 is not None
        and feature.elevated_day_ratio_20 >= thresholds.elevated_day_ratio_min
    )
    excess = feature.excess_return_st_20
    compression = feature.range_compression_20
    single_day_jump = bool(
        single_day_strict
        and feature.single_day_excess_return_st is not None
        and feature.single_day_excess_return_st >= thresholds.single_day_excess_return_min
        and feature.single_day_amplitude_ratio is not None
        and feature.single_day_amplitude_ratio >= thresholds.single_day_amplitude_ratio_min
    )
    if single_day_jump:
        label = "single_day_activity_price_jump"
        reasons = ["单日 strict 活跃偏离", "当日相对 ST 上涨且振幅扩张"]
    elif persistent and excess is not None and excess <= thresholds.down_excess_return_max:
        label = "persistent_activity_price_down"
        reasons = ["累计自由流通换手高于自身历史", "相对 ST 等权价格下行"]
    elif (
        persistent and excess is not None
        and abs(excess) <= thresholds.stable_abs_excess_return_max
        and compression is not None and compression <= thresholds.range_compression_max
    ):
        label = "persistent_activity_price_stable"
        reasons = ["累计自由流通换手高于自身历史", "相对价格平稳且振幅未扩张"]
    else:
        label = "quiet"
        reasons = ["未满足冻结的持续型或单日形态条件"]
    return ShapeLabel(
        feature_id=feature.feature_id, profile=thresholds.profile,
        label=label, reasons=reasons,
    )


def profile_capacity(
    features: list[P8ActivityFeature], *,
    strict_feature_ids: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    strict_ids = strict_feature_ids or set()
    days = sorted({item.trade_date for item in features})
    result: dict[str, dict[str, Any]] = {}
    for profile in FROZEN_SHAPE_PROFILES:
        labels = [
            classify_shape(item, profile, single_day_strict=item.feature_id in strict_ids)
            for item in features
        ]
        by_id = {item.feature_id: item for item in features}
        active = [
            item for item in labels
            if item.label not in {"quiet", "unknown"}
        ]
        daily = Counter(by_id[item.feature_id].trade_date for item in active)
        counts = sorted(daily.get(day, 0) for day in days)
        result[profile.profile] = {
            "thresholds": profile.model_dump(mode="json"),
            "calculable_count": sum(item.calculable for item in features),
            "candidate_count": len(active),
            "company_count": len({by_id[item.feature_id].symbol for item in active}),
            "daily_mean": round(statistics.mean(counts), 6) if counts else 0.0,
            "daily_median": statistics.median(counts) if counts else 0.0,
            "daily_p90": counts[int((len(counts) - 1) * .90)] if counts else 0,
            "daily_max": max(counts, default=0),
            "label_counts": dict(sorted(Counter(item.label for item in labels).items())),
        }
    return result


def choose_capacity_profile(capacity: dict[str, dict[str, Any]]) -> str:
    """Choose by coverage/capacity only; no outcome input exists in this API."""
    eligible = [
        name for name, values in capacity.items()
        if values["daily_median"] <= 20 and values["daily_p90"] <= 30
    ]
    if not eligible:
        return "unavailable"
    strictness = {"broad": 0, "base": 1, "strict": 2}
    eligible.sort(key=lambda name: (
        capacity[name]["company_count"], capacity[name]["candidate_count"], strictness[name]
    ), reverse=True)
    return eligible[0]
