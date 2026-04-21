from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MetricSummary:
    mae: float | None
    rmse: float | None
    wape: float | None
    mape: float | None
    bias: float | None
    interval_coverage: float | None


def _safe_mean(values: Iterable[float]) -> float | None:
    values_list = list(values)
    if not values_list:
        return None
    return float(np.mean(values_list))


def compute_regression_metrics(
    actual: Iterable[float],
    predicted: Iterable[float],
    lower: Iterable[float] | None = None,
    upper: Iterable[float] | None = None,
) -> MetricSummary:
    actual_array = np.asarray(list(actual), dtype=float)
    predicted_array = np.asarray(list(predicted), dtype=float)
    if actual_array.size == 0:
        return MetricSummary(None, None, None, None, None, None)

    errors = predicted_array - actual_array
    abs_errors = np.abs(errors)
    mae = float(np.mean(abs_errors))
    rmse = float(sqrt(np.mean(np.square(errors))))

    actual_total = float(np.sum(np.abs(actual_array)))
    wape = float(np.sum(abs_errors) / actual_total) if actual_total else None

    nonzero_mask = actual_array != 0
    mape = (
        float(np.mean(np.abs(errors[nonzero_mask] / actual_array[nonzero_mask])))
        if np.any(nonzero_mask)
        else None
    )

    actual_sum = float(np.sum(actual_array))
    bias = float(np.sum(errors) / actual_sum) if actual_sum else None

    if lower is None or upper is None:
        interval_coverage = None
    else:
        lower_array = np.asarray(list(lower), dtype=float)
        upper_array = np.asarray(list(upper), dtype=float)
        interval_coverage = float(
            np.mean((actual_array >= lower_array) & (actual_array <= upper_array))
        )

    return MetricSummary(mae, rmse, wape, mape, bias, interval_coverage)


def compute_direction_accuracy(
    actual: pd.Series,
    predicted: pd.Series,
    previous_actual: pd.Series,
) -> float | None:
    if actual.empty:
        return None

    actual_delta = actual.astype(float) - previous_actual.astype(float)
    predicted_delta = predicted.astype(float) - previous_actual.astype(float)

    def direction(delta: pd.Series) -> pd.Series:
        return pd.Series(np.where(delta > 0, 1, np.where(delta < 0, -1, 0)), index=delta.index)

    actual_direction = direction(actual_delta)
    predicted_direction = direction(predicted_delta)
    return float((actual_direction == predicted_direction).mean())


def compute_stockout_risk_proxy(
    predicted: pd.Series,
    stock_level: float | None,
) -> float | None:
    if stock_level is None:
        return None
    if stock_level <= 0:
        return float((predicted.astype(float) > 0).mean())
    return float((predicted.astype(float) > stock_level).mean())


def compute_baseline_predictions(history_values: pd.Series, horizon_length: int, window: int) -> list[float]:
    if history_values.empty:
        return [0.0 for _ in range(horizon_length)]
    window_values = history_values.astype(float).tail(window)
    baseline = float(window_values.mean())
    return [baseline for _ in range(horizon_length)]


def evaluate_trend_justification(history_values: pd.Series) -> tuple[float | None, float | None]:
    if history_values.empty:
        return None, None
    recent = history_values.astype(float).tail(min(4, len(history_values)))
    recent_average = float(recent.mean()) if not recent.empty else None
    recent_trend = float(recent.iloc[-1] - recent.iloc[0]) if len(recent) >= 2 else None
    return recent_average, recent_trend


