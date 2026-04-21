from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

import pandas as pd

from apps.forecast_service.app.services.model import (
    MIN_YEARLY_SEASONALITY_POINTS,
    MODEL_PATH_FALLBACK_RECENT_TREND,
    MODEL_PATH_FALLBACK_UNSAFE_PROPHET,
    MODEL_PATH_FALLBACK_UNSAFE_XGBOOST,
    MODEL_PATH_PROPHET,
    MODEL_PATH_XGBOOST_RESIDUAL,
    build_ontario_holidays,
    build_xgboost_training_frame,
    complete_weekly_history,
    fallback_weekly_forecast,
    forecast_has_unsafe_values,
    history_supports_prophet,
    history_supports_xgboost,
    normalize_weekly_history,
    recursive_xgboost_point_forecast,
    xgboost_boost_rounds,
    xgboost_feature_columns,
    xgboost_point_params,
    xgboost_residual_spread,
)
from forecasting.exceptions import BacktestError


@dataclass(frozen=True)
class ForecastPeriod:
    forecast_date: date
    yhat: float
    yhat_lower: float | None
    yhat_upper: float | None


class ForecastGenerator(Protocol):
    def forecast(self, train_rows: pd.DataFrame, horizon_length: int) -> pd.DataFrame:
        """Return one row per forecast period with forecast_date and interval columns."""


class XGBoostForecastGenerator:
    """Weekly XGBoost forecaster that mirrors the production numeric forecast settings."""

    def forecast(self, train_rows: pd.DataFrame, horizon_length: int) -> pd.DataFrame:
        history = complete_weekly_history(normalize_weekly_history(train_rows.to_dict(orient="records")))
        if history.empty:
            raise BacktestError("empty_training_history")

        if not history_supports_xgboost(history):
            return _forecast_frame_from_model_frame(
                fallback_weekly_forecast(history, horizon_length),
                model_path=MODEL_PATH_FALLBACK_RECENT_TREND,
            )

        train_frame = build_xgboost_training_frame(history)
        if train_frame.empty:
            return _forecast_frame_from_model_frame(
                fallback_weekly_forecast(history, horizon_length),
                model_path=MODEL_PATH_FALLBACK_RECENT_TREND,
            )

        try:
            import xgboost as xgb
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise BacktestError("forecast_dependencies_missing") from exc

        features = train_frame[xgboost_feature_columns()].to_numpy(dtype=float)
        target = train_frame["target"].to_numpy(dtype=float)
        matrix = xgb.DMatrix(features, target)
        booster = xgb.train(
            xgboost_point_params(),
            matrix,
            num_boost_round=xgboost_boost_rounds(len(train_frame)),
            verbose_eval=False,
        )
        residual_spread = xgboost_residual_spread(target, booster.inplace_predict(features))
        forecast = recursive_xgboost_point_forecast(
            booster=booster,
            history=history,
            horizon_periods=horizon_length,
            residual_spread=residual_spread,
        )
        if forecast_has_unsafe_values(forecast):
            return _forecast_frame_from_model_frame(
                fallback_weekly_forecast(history, horizon_length),
                model_path=MODEL_PATH_FALLBACK_UNSAFE_XGBOOST,
            )
        return _forecast_frame_from_model_frame(forecast, model_path=MODEL_PATH_XGBOOST_RESIDUAL)


class ProphetForecastGenerator:
    """Weekly Prophet forecaster that mirrors the production numeric forecast settings."""

    def forecast(self, train_rows: pd.DataFrame, horizon_length: int) -> pd.DataFrame:
        history = normalize_weekly_history(train_rows.to_dict(orient="records"))
        if history.empty:
            raise BacktestError("empty_training_history")

        if len(history) < 2:
            return _naive_forecast(history, horizon_length)
        if not history_supports_prophet(history):
            return _forecast_frame_from_model_frame(
                fallback_weekly_forecast(history, horizon_length),
                model_path=MODEL_PATH_FALLBACK_RECENT_TREND,
            )

        try:
            from prophet import Prophet
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise BacktestError("forecast_dependencies_missing") from exc

        holidays = pd.DataFrame(
            build_ontario_holidays(int(history["ds"].dt.year.min()), int(history["ds"].dt.year.max()) + 2)
        )
        model = Prophet(
            yearly_seasonality=len(history) >= MIN_YEARLY_SEASONALITY_POINTS,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            holidays=holidays if len(history) >= MIN_YEARLY_SEASONALITY_POINTS else None,
        )

        try:
            model.fit(history)
            future = model.make_future_dataframe(periods=horizon_length, freq="W-MON", include_history=False)
            forecast = model.predict(future)
        except Exception:
            return _naive_forecast(history, horizon_length)
        if forecast_has_unsafe_values(forecast):
            return _forecast_frame_from_model_frame(
                fallback_weekly_forecast(history, horizon_length),
                model_path=MODEL_PATH_FALLBACK_UNSAFE_PROPHET,
            )

        return forecast.rename(
            columns={"ds": "forecast_date", "yhat": "yhat", "yhat_lower": "yhat_lower", "yhat_upper": "yhat_upper"}
        ).assign(model_path=MODEL_PATH_PROPHET)[["forecast_date", "yhat", "yhat_lower", "yhat_upper", "model_path"]]


def _naive_forecast(history: pd.DataFrame, horizon_length: int) -> pd.DataFrame:
    last_date = history["ds"].iloc[-1]
    future_dates = pd.date_range(start=last_date + timedelta(days=7), periods=horizon_length, freq="W-MON")
    recent = history["y"].tail(min(4, len(history))).astype(float)
    center = float(recent.mean()) if not recent.empty else 0.0
    spread = float(recent.std(ddof=0)) if len(recent) > 1 else max(1.0, center * 0.1)
    lower = max(0.0, center - 1.96 * spread)
    upper = max(center + 1.96 * spread, center)
    return pd.DataFrame(
        {
            "forecast_date": [ts.date() for ts in future_dates],
            "yhat": [center for _ in range(horizon_length)],
            "yhat_lower": [lower for _ in range(horizon_length)],
            "yhat_upper": [upper for _ in range(horizon_length)],
            "model_path": [MODEL_PATH_FALLBACK_RECENT_TREND for _ in range(horizon_length)],
        }
    )


def _forecast_frame_from_model_frame(frame: pd.DataFrame, model_path: str) -> pd.DataFrame:
    return frame.rename(
        columns={"ds": "forecast_date", "yhat": "yhat", "yhat_lower": "yhat_lower", "yhat_upper": "yhat_upper"}
    ).assign(model_path=model_path)[["forecast_date", "yhat", "yhat_lower", "yhat_upper", "model_path"]]
