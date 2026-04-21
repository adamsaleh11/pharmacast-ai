from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Protocol

import numpy as np

from apps.forecast_service.app.services.domain import ForecastPrediction, ForecastingError

MIN_PROPHET_HISTORY_POINTS = 26
MIN_YEARLY_SEASONALITY_POINTS = 104
RECENT_AVERAGE_WINDOW = 2


class ForecastModelRunner(Protocol):
    def forecast(self, weekly_rows: list[dict[str, Any]], horizon_days: int) -> ForecastPrediction:
        ...


class ProphetModelRunner:
    def forecast(self, weekly_rows: list[dict[str, Any]], horizon_days: int) -> ForecastPrediction:
        try:
            import pandas as pd
            from prophet import Prophet
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise ForecastingError("forecast_dependencies_missing") from exc

        if not weekly_rows:
            raise ForecastingError("insufficient_weekly_data")

        frame = normalize_weekly_history(weekly_rows)
        horizon_weeks = max(1, (horizon_days + 6) // 7)
        if not history_supports_prophet(frame):
            fallback_window = fallback_weekly_forecast(frame, horizon_weeks)
            return summarize_horizon_forecast(fallback_window, horizon_periods=horizon_weeks)

        holidays = pd.DataFrame(
            build_ontario_holidays(int(frame["ds"].dt.year.min()), int(frame["ds"].dt.year.max()) + 2)
        )

        model = Prophet(
            yearly_seasonality=len(frame) >= MIN_YEARLY_SEASONALITY_POINTS,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            holidays=holidays if len(frame) >= MIN_YEARLY_SEASONALITY_POINTS else None,
        )
        model.fit(frame)

        future = model.make_future_dataframe(periods=horizon_weeks, freq="W-MON", include_history=False)
        forecast = model.predict(future)
        if forecast_has_unsafe_values(forecast):
            forecast = fallback_weekly_forecast(frame, horizon_weeks)
            samples = None
        else:
            samples = model.predictive_samples(future)
        interval_width = getattr(model, "interval_width", 0.8)
        return summarize_horizon_forecast(
            forecast,
            horizon_periods=horizon_weeks,
            interval_width=float(interval_width),
            predictive_samples=samples,
        )


def normalize_weekly_history(records: list[dict[str, Any]]) -> Any:
    import pandas as pd

    frame = pd.DataFrame(records)
    if {"dispensed_date", "quantity_dispensed"}.issubset(frame.columns):
        frame = frame.rename(columns={"dispensed_date": "ds", "quantity_dispensed": "y"})[["ds", "y"]]
    elif {"ds", "y"}.issubset(frame.columns):
        frame = frame[["ds", "y"]]
    else:
        raise ForecastingError("invalid_forecast_history")

    frame["ds"] = pd.to_datetime(frame["ds"])
    frame["ds"] = frame["ds"].dt.to_period("W").apply(lambda period: period.start_time)
    return frame.groupby("ds", as_index=False)["y"].sum().sort_values("ds").reset_index(drop=True)


def history_supports_prophet(frame: Any) -> bool:
    return len(frame) >= MIN_PROPHET_HISTORY_POINTS and float(frame["y"].astype(float).sum()) > 0.0


def forecast_has_unsafe_values(frame: Any) -> bool:
    columns = [column for column in ["yhat", "yhat_lower", "yhat_upper"] if column in frame]
    if not columns:
        return True
    values = frame[columns].to_numpy(dtype=float)
    return bool(np.isnan(values).any() or np.isinf(values).any() or (values < 0).any())


def fallback_weekly_forecast(frame: Any, horizon_periods: int) -> Any:
    import pandas as pd

    predictions = _fallback_weekly_predictions(frame, horizon_periods)
    center = float(np.mean(predictions)) if predictions else 0.0
    residual_basis = frame["y"].astype(float).tail(min(8, len(frame)))
    spread = float(residual_basis.std(ddof=0)) if len(residual_basis) > 1 else max(1.0, center * 0.1)
    last_date = pd.to_datetime(frame["ds"].iloc[-1])
    dates = pd.date_range(start=last_date + pd.Timedelta(days=7), periods=horizon_periods, freq="W-MON")
    return pd.DataFrame(
        {
            "ds": dates,
            "yhat": predictions,
            "yhat_lower": [max(0.0, value - 1.96 * spread) for value in predictions],
            "yhat_upper": [max(value + 1.96 * spread, value) for value in predictions],
        }
    )


def _fallback_weekly_predictions(frame: Any, horizon_periods: int) -> list[float]:
    values = frame["y"].astype(float).tolist()
    if not values:
        return [0.0 for _ in range(horizon_periods)]

    recent = values[-min(RECENT_AVERAGE_WINDOW, len(values)) :]
    center = max(0.0, float(np.mean(recent)))
    slope = _recent_trend_slope(values)
    if slope is None:
        return [center for _ in range(horizon_periods)]

    material_slope = max(2.0, center * 0.03)
    if abs(slope) < material_slope:
        return [center for _ in range(horizon_periods)]

    last_value = max(0.0, float(values[-1]))
    return [max(0.0, last_value + (period + 1) * slope * 0.5) for period in range(horizon_periods)]


def _recent_trend_slope(values: list[float]) -> float | None:
    if len(values) < 4:
        return None
    recent = np.asarray(values[-4:], dtype=float)
    x = np.arange(len(recent), dtype=float)
    slope, _intercept = np.polyfit(x, recent, deg=1)
    return float(slope)


def summarize_horizon_forecast(
    forecast_window: Any,
    horizon_periods: int,
    interval_width: float = 0.8,
    predictive_samples: Any | None = None,
) -> ForecastPrediction:
    predicted_total = _sum_column(forecast_window, "yhat")

    lower_total: float
    upper_total: float
    sample_totals = _aggregate_sample_totals(predictive_samples, horizon_periods)
    if sample_totals.size:
        tail_probability = max(0.0, min(0.49, (1.0 - interval_width) / 2.0))
        lower_total = float(np.quantile(sample_totals, tail_probability))
        upper_total = float(np.quantile(sample_totals, 1.0 - tail_probability))
    else:
        lower_total = _sum_column(forecast_window, "yhat_lower")
        upper_total = _sum_column(forecast_window, "yhat_upper")

    predicted_quantity, prophet_lower, prophet_upper = _sanitize_prediction_interval(
        predicted_total=predicted_total,
        lower_total=lower_total,
        upper_total=upper_total,
    )
    confidence = _confidence_from_interval(predicted_quantity, prophet_lower, prophet_upper)

    return ForecastPrediction(
        predicted_quantity=predicted_quantity,
        prophet_lower=prophet_lower,
        prophet_upper=prophet_upper,
        confidence=confidence,
    )


def _sum_column(frame: Any, column: str) -> float:
    return float(frame[column].sum())


def _aggregate_sample_totals(predictive_samples: Any | None, horizon_periods: int) -> np.ndarray:
    if predictive_samples is None:
        return np.array([])

    raw_samples = predictive_samples["yhat"] if isinstance(predictive_samples, dict) else predictive_samples
    samples = np.asarray(raw_samples, dtype=float)
    if samples.ndim != 2:
        return np.array([])

    if samples.shape[0] == horizon_periods:
        return samples.sum(axis=0)
    if samples.shape[1] == horizon_periods:
        return samples.sum(axis=1)
    return np.array([])


def _sanitize_prediction_interval(
    predicted_total: float, lower_total: float, upper_total: float
) -> tuple[int, int, int]:
    predicted_quantity = max(0, int(round(float(predicted_total))))
    prophet_lower = max(0, int(round(float(lower_total))))
    prophet_upper = max(0, int(round(float(upper_total))))

    if prophet_upper < prophet_lower:
        prophet_upper = prophet_lower
    if predicted_quantity < prophet_lower:
        prophet_lower = predicted_quantity
    if predicted_quantity > prophet_upper:
        prophet_upper = predicted_quantity

    return predicted_quantity, prophet_lower, prophet_upper


def _confidence_from_interval(predicted_quantity: int, prophet_lower: int, prophet_upper: int) -> str:
    width_ratio = (prophet_upper - prophet_lower) / max(predicted_quantity, 1)
    if width_ratio < 0.3:
        return "HIGH"
    if width_ratio < 0.6:
        return "MEDIUM"
    return "LOW"


def build_ontario_holidays(start_year: int, end_year: int) -> list[dict[str, Any]]:
    holidays: list[dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        holidays.extend(
            [
                {"ds": date(year, 1, 1), "holiday": "new_years_day"},
                {"ds": nth_weekday_of_month(year, 2, 0, 3), "holiday": "family_day"},
                {"ds": good_friday(year), "holiday": "good_friday"},
                {"ds": last_weekday_on_or_before(date(year, 5, 25), 0), "holiday": "victoria_day"},
                {"ds": date(year, 7, 1), "holiday": "canada_day"},
                {"ds": nth_weekday_of_month(year, 8, 0, 1), "holiday": "civic_holiday"},
                {"ds": nth_weekday_of_month(year, 9, 0, 1), "holiday": "labour_day"},
                {"ds": nth_weekday_of_month(year, 10, 0, 2), "holiday": "thanksgiving"},
                {"ds": date(year, 11, 11), "holiday": "remembrance_day"},
                {"ds": date(year, 12, 25), "holiday": "christmas_day"},
                {"ds": date(year, 12, 26), "holiday": "boxing_day"},
            ]
        )
    return holidays


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def last_weekday_on_or_before(start: date, weekday: int) -> date:
    offset = (start.weekday() - weekday) % 7
    return start - timedelta(days=offset)


def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def good_friday(year: int) -> date:
    return easter_sunday(year) - timedelta(days=2)
