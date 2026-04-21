from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import uuid

import numpy as np
import pandas as pd

from forecasting.data import (
    FORECAST_COLUMN_ORDER,
    aggregate_weekly,
    load_input_csv,
    load_stock_levels,
    validate_no_leakage,
)
from forecasting.exceptions import BacktestSchemaError
from forecasting.metrics import (
    compute_baseline_predictions,
    compute_direction_accuracy,
    compute_regression_metrics,
    compute_stockout_risk_proxy,
    evaluate_trend_justification,
)
from forecasting.model import ForecastGenerator, ProphetForecastGenerator
from forecasting.reporting import ensure_output_dir, write_dataframe_artifacts, write_json_artifact


MIN_HISTORY_POINTS = 8
DEFAULT_BASELINE_WINDOW_7 = 1
DEFAULT_BASELINE_WINDOW_14 = 2


@dataclass(frozen=True)
class BacktestRunConfig:
    train_path: Path
    actual_path: Path
    backtest_name: str
    model_version: str
    outdir: Path
    forecast_horizon: int
    stock_levels_path: Path | None = None
    minimum_history_points: int = MIN_HISTORY_POINTS


@dataclass(frozen=True)
class BacktestRunResult:
    run_id: str
    config: BacktestRunConfig
    forecast_rows: pd.DataFrame
    din_metrics: pd.DataFrame
    global_metrics: dict[str, Any]
    anomalies: pd.DataFrame
    summary: dict[str, Any]
    artifact_paths: dict[str, Path]


class BacktestRunner:
    def __init__(
        self,
        forecaster: ForecastGenerator | None = None,
    ) -> None:
        self.forecaster = forecaster or ProphetForecastGenerator()

    def run(self, config: BacktestRunConfig) -> BacktestRunResult:
        started_at = datetime.now(timezone.utc)
        train_raw = load_input_csv(config.train_path)
        actual_raw = load_input_csv(config.actual_path)
        validate_no_leakage(train_raw, actual_raw)

        train = aggregate_weekly(train_raw)
        actual = aggregate_weekly(actual_raw)
        stock_levels = load_stock_levels(config.stock_levels_path)

        actual_dates = sorted(pd.to_datetime(actual["dispensed_date"]).dt.date.unique().tolist())
        if len(actual_dates) != config.forecast_horizon:
            raise BacktestSchemaError(
                f"forecast_horizon_mismatch:expected={config.forecast_horizon},actual={len(actual_dates)}"
            )

        train_hash = _file_hash(config.train_path)
        actual_hash = _file_hash(config.actual_path)
        run_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "|".join(
                    [
                        config.backtest_name,
                        config.model_version,
                        str(config.forecast_horizon),
                        train_hash,
                        actual_hash,
                    ]
                ),
            )
        )
        generated_at = started_at.isoformat()

        rows: list[dict[str, Any]] = []
        din_metrics_rows: list[dict[str, Any]] = []
        anomaly_rows: list[dict[str, Any]] = []
        all_actual_values: list[float] = []
        all_predicted_values: list[float] = []
        all_lower_values: list[float] = []
        all_upper_values: list[float] = []
        all_previous_actual_values: list[float] = []
        all_baseline_7_values: list[float] = []
        all_baseline_14_values: list[float] = []
        all_stockout_proxy_values: list[float] = []

        for din in sorted(actual["din"].astype(str).unique().tolist()):
            train_din = train.loc[train["din"].astype(str) == din].copy()
            actual_din = actual.loc[actual["din"].astype(str) == din].copy()

            if train_din.empty:
                raise BacktestSchemaError(f"missing_train_history_for_din:{din}")
            if actual_din.empty:
                raise BacktestSchemaError(f"missing_actual_history_for_din:{din}")

            train_start_date = pd.to_datetime(train_din["dispensed_date"]).dt.date.min().isoformat()
            train_end_date = pd.to_datetime(train_din["dispensed_date"]).dt.date.max().isoformat()
            history_points_used = int(len(train_din))
            horizon_length = int(len(actual_din))

            forecast_frame = self.forecaster.forecast(train_din, horizon_length=horizon_length)
            forecast_frame = _normalize_forecast_frame(forecast_frame)

            actual_lookup = {
                pd.to_datetime(row["dispensed_date"]).date(): float(row["quantity_dispensed"])
                for row in actual_din.to_dict(orient="records")
            }
            actual_dates_for_din = sorted(actual_lookup)
            forecast_dates = list(forecast_frame["forecast_date"])
            if forecast_dates != actual_dates_for_din:
                raise BacktestSchemaError(
                    f"forecast_date_mismatch_for_din:{din}:{forecast_dates[:3]} != {actual_dates_for_din[:3]}"
                )

            actual_series = pd.Series([actual_lookup[forecast_date] for forecast_date in forecast_dates])
            predicted_series = forecast_frame["yhat"].astype(float)
            lower_series = forecast_frame["yhat_lower"].astype(float)
            upper_series = forecast_frame["yhat_upper"].astype(float)

            baseline_7 = compute_baseline_predictions(train_din["quantity_dispensed"], horizon_length, window=1)
            baseline_14 = compute_baseline_predictions(train_din["quantity_dispensed"], horizon_length, window=2)
            baseline_7_metrics = compute_regression_metrics(actual_series, baseline_7)
            baseline_14_metrics = compute_regression_metrics(actual_series, baseline_14)
            model_metrics = compute_regression_metrics(actual_series, predicted_series, lower_series, upper_series)
            previous_actual_series = _previous_actual_series(train_din["quantity_dispensed"], actual_series)
            direction_accuracy = compute_direction_accuracy(
                actual_series,
                predicted_series,
                previous_actual_series,
            )
            stockout_risk_proxy = compute_stockout_risk_proxy(
                predicted_series,
                stock_levels.get(din) if stock_levels else None,
            )
            if stock_levels and stock_levels.get(din) is not None:
                stock_level = stock_levels[din]
                all_stockout_proxy_values.extend([1.0 if float(value) > stock_level else 0.0 for value in predicted_series])
            overforecast_units = float(np.maximum(predicted_series - actual_series, 0).sum())
            underforecast_units = float(np.maximum(actual_series - predicted_series, 0).sum())

            best_baseline_name, best_baseline_metrics = _best_baseline_metrics(
                baseline_7_metrics, baseline_14_metrics
            )

            all_actual_values.extend(actual_series.astype(float).tolist())
            all_predicted_values.extend(predicted_series.astype(float).tolist())
            all_lower_values.extend(lower_series.astype(float).tolist())
            all_upper_values.extend(upper_series.astype(float).tolist())
            all_previous_actual_values.extend(previous_actual_series.astype(float).tolist())
            all_baseline_7_values.extend(baseline_7)
            all_baseline_14_values.extend(baseline_14)

            din_metrics_rows.append(
                {
                    "run_id": run_id,
                    "model_version": config.model_version,
                    "backtest_name": config.backtest_name,
                    "din": din,
                    "rows_evaluated": horizon_length,
                    "history_points_used": history_points_used,
                    "mae": model_metrics.mae,
                    "rmse": model_metrics.rmse,
                    "wape": model_metrics.wape,
                    "mape": model_metrics.mape,
                    "bias": model_metrics.bias,
                    "interval_coverage": model_metrics.interval_coverage,
                    "direction_accuracy": direction_accuracy,
                    "stockout_risk_proxy": stockout_risk_proxy,
                    "overforecast_units": overforecast_units,
                    "underforecast_units": underforecast_units,
                    "baseline_last_7_day_avg_mae": baseline_7_metrics.mae,
                    "baseline_last_14_day_avg_mae": baseline_14_metrics.mae,
                    "beats_last_7_day_avg": _is_better(model_metrics.mae, baseline_7_metrics.mae),
                    "beats_last_14_day_avg": _is_better(model_metrics.mae, baseline_14_metrics.mae),
                    "beats_best_baseline": _is_better(model_metrics.mae, best_baseline_metrics.mae),
                    "best_baseline_name": best_baseline_name,
                }
            )

            recent_average, recent_trend = evaluate_trend_justification(train_din["quantity_dispensed"])
            for index, row in forecast_frame.iterrows():
                forecast_date = row["forecast_date"]
                yhat = float(row["yhat"])
                yhat_lower = float(row["yhat_lower"]) if pd.notna(row["yhat_lower"]) else None
                yhat_upper = float(row["yhat_upper"]) if pd.notna(row["yhat_upper"]) else None
                anomaly_flag, anomaly_reason = _detect_anomalies(
                    yhat=yhat,
                    yhat_lower=yhat_lower,
                    yhat_upper=yhat_upper,
                    history_points_used=history_points_used,
                    minimum_history_points=config.minimum_history_points,
                    recent_average=recent_average,
                    recent_trend=recent_trend,
                )
                actual_quantity = float(actual_lookup[forecast_date])
                row_payload = {
                    "run_id": run_id,
                    "model_version": config.model_version,
                    "backtest_name": config.backtest_name,
                    "generated_at": generated_at,
                    "din": din,
                    "forecast_date": forecast_date.isoformat(),
                    "yhat": round(yhat, 2),
                    "yhat_lower": round(yhat_lower, 2) if yhat_lower is not None else None,
                    "yhat_upper": round(yhat_upper, 2) if yhat_upper is not None else None,
                    "actual_quantity": actual_quantity,
                    "train_start_date": train_start_date,
                    "train_end_date": train_end_date,
                    "horizon_length": horizon_length,
                    "history_points_used": history_points_used,
                    "confidence_label": _confidence_label(yhat, yhat_lower, yhat_upper),
                    "anomaly_flag": anomaly_flag,
                    "anomaly_reason": anomaly_reason,
                }
                rows.append(row_payload)
                if anomaly_flag:
                    anomaly_rows.append(row_payload)

        forecast_rows = pd.DataFrame(rows)
        forecast_rows = forecast_rows.reindex(columns=FORECAST_COLUMN_ORDER)
        anomalies = pd.DataFrame(anomaly_rows).reindex(columns=FORECAST_COLUMN_ORDER) if anomaly_rows else pd.DataFrame(columns=FORECAST_COLUMN_ORDER)
        din_metrics = pd.DataFrame(din_metrics_rows)

        global_metrics = _global_metrics(
            actual_values=all_actual_values,
            predicted_values=all_predicted_values,
            lower_values=all_lower_values,
            upper_values=all_upper_values,
            previous_actual_values=all_previous_actual_values,
            baseline_7_values=all_baseline_7_values,
            baseline_14_values=all_baseline_14_values,
            stockout_proxy_values=all_stockout_proxy_values,
            forecast_date_count=len(actual_dates),
            din_metrics=din_metrics,
            run_id=run_id,
            model_version=config.model_version,
            backtest_name=config.backtest_name,
        )
        summary = _build_summary(global_metrics, forecast_rows, anomalies, config, started_at, run_id)

        output_dir = ensure_output_dir(config.outdir)
        artifact_paths = {
            "forecast_rows_csv": output_dir / "forecast_rows.csv",
            "forecast_rows_json": output_dir / "forecast_rows.json",
            "din_metrics_csv": output_dir / "din_metrics.csv",
            "global_metrics_json": output_dir / "global_metrics.json",
            "anomalies_csv": output_dir / "anomalies.csv",
            "backtest_summary_csv": output_dir / "backtest_summary.csv",
            "backtest_summary_json": output_dir / "backtest_summary.json",
        }
        write_dataframe_artifacts(forecast_rows, artifact_paths["forecast_rows_csv"], artifact_paths["forecast_rows_json"])
        write_dataframe_artifacts(din_metrics, artifact_paths["din_metrics_csv"])
        write_json_artifact(global_metrics, artifact_paths["global_metrics_json"])
        write_dataframe_artifacts(anomalies, artifact_paths["anomalies_csv"])
        write_dataframe_artifacts(pd.DataFrame([summary]), artifact_paths["backtest_summary_csv"])
        write_json_artifact(summary, artifact_paths["backtest_summary_json"])

        return BacktestRunResult(
            run_id=run_id,
            config=config,
            forecast_rows=forecast_rows,
            din_metrics=din_metrics,
            global_metrics=global_metrics,
            anomalies=anomalies,
            summary=summary,
            artifact_paths=artifact_paths,
        )


def _normalize_forecast_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["forecast_date"] = pd.to_datetime(normalized["forecast_date"]).dt.date
    normalized["yhat"] = pd.to_numeric(normalized["yhat"], errors="raise")
    normalized["yhat_lower"] = pd.to_numeric(normalized["yhat_lower"], errors="coerce")
    normalized["yhat_upper"] = pd.to_numeric(normalized["yhat_upper"], errors="coerce")
    return normalized.sort_values("forecast_date").reset_index(drop=True)


def _previous_actual_series(train_values: pd.Series, actual_values: pd.Series) -> pd.Series:
    history_tail = train_values.astype(float).tail(1).tolist()
    previous_values = history_tail + actual_values.astype(float).tolist()[:-1]
    return pd.Series(previous_values, index=actual_values.index)


def _confidence_label(yhat: float, yhat_lower: float | None, yhat_upper: float | None) -> str:
    if yhat_lower is None or yhat_upper is None:
        return "LOW"
    width = max(0.0, float(yhat_upper) - float(yhat_lower))
    ratio = width / max(abs(float(yhat)), 1.0)
    if ratio < 0.3:
        return "HIGH"
    if ratio < 0.6:
        return "MEDIUM"
    return "LOW"


def _detect_anomalies(
    *,
    yhat: float,
    yhat_lower: float | None,
    yhat_upper: float | None,
    history_points_used: int,
    minimum_history_points: int,
    recent_average: float | None,
    recent_trend: float | None,
) -> tuple[bool, str | None]:
    reasons: list[str] = []
    if yhat < 0:
        reasons.append("negative_prediction")
    if yhat_lower is None or yhat_upper is None:
        reasons.append("missing_bounds")
    else:
        if yhat_lower > yhat:
            reasons.append("lower_bound_above_prediction")
        if yhat > yhat_upper:
            reasons.append("prediction_above_upper_bound")
    if history_points_used < minimum_history_points:
        reasons.append("insufficient_history")
    if recent_average is not None and recent_average > 0 and yhat > 2.5 * recent_average:
        if recent_trend is None or recent_trend <= 0:
            reasons.append("spike_without_supporting_trend")
    return bool(reasons), ";".join(reasons) if reasons else None


def _best_baseline_metrics(first, second):
    if first.mae is None:
        return "last_14_day_avg", second
    if second.mae is None:
        return "last_7_day_avg", first
    if first.mae <= second.mae:
        return "last_7_day_avg", first
    return "last_14_day_avg", second


def _is_better(model_mae: float | None, baseline_mae: float | None) -> bool | None:
    if model_mae is None or baseline_mae is None:
        return None
    return model_mae < baseline_mae


def _global_metrics(
    *,
    actual_values: list[float],
    predicted_values: list[float],
    lower_values: list[float],
    upper_values: list[float],
    previous_actual_values: list[float],
    baseline_7_values: list[float],
    baseline_14_values: list[float],
    stockout_proxy_values: list[float],
    forecast_date_count: int,
    din_metrics: pd.DataFrame,
    run_id: str,
    model_version: str,
    backtest_name: str,
) -> dict[str, Any]:
    metrics = compute_regression_metrics(actual_values, predicted_values, lower_values, upper_values)
    baseline_7_metrics = compute_regression_metrics(actual_values, baseline_7_values)
    baseline_14_metrics = compute_regression_metrics(actual_values, baseline_14_values)
    direction_accuracy = (
        compute_direction_accuracy(
            pd.Series(actual_values),
            pd.Series(predicted_values),
            pd.Series(previous_actual_values),
        )
        if actual_values
        else None
    )

    stockout_risk_proxy = float(np.mean(stockout_proxy_values)) if stockout_proxy_values else None

    beats_7 = _is_better(metrics.mae, baseline_7_metrics.mae)
    beats_14 = _is_better(metrics.mae, baseline_14_metrics.mae)
    if not din_metrics.empty:
        beats_7_values = din_metrics["beats_last_7_day_avg"].dropna()
        beats_14_values = din_metrics["beats_last_14_day_avg"].dropna()
        beats_7_count = int(beats_7_values.sum()) if not beats_7_values.empty else 0
        beats_14_count = int(beats_14_values.sum()) if not beats_14_values.empty else 0
    else:
        beats_7_count = 0
        beats_14_count = 0

    return {
        "run_id": run_id,
        "model_version": model_version,
        "backtest_name": backtest_name,
        "rows_evaluated": int(len(actual_values)),
        "din_count": int(din_metrics["din"].nunique()) if not din_metrics.empty else 0,
        "forecast_date_count": int(forecast_date_count),
        "mae": metrics.mae,
        "rmse": metrics.rmse,
        "wape": metrics.wape,
        "mape": metrics.mape,
        "bias": metrics.bias,
        "interval_coverage": metrics.interval_coverage,
        "direction_accuracy": direction_accuracy,
        "stockout_risk_proxy": stockout_risk_proxy,
        "overforecast_units": float(np.maximum(np.asarray(predicted_values) - np.asarray(actual_values), 0).sum())
        if actual_values
        else None,
        "underforecast_units": float(np.maximum(np.asarray(actual_values) - np.asarray(predicted_values), 0).sum())
        if actual_values
        else None,
        "baseline_last_7_day_avg_mae": baseline_7_metrics.mae,
        "baseline_last_14_day_avg_mae": baseline_14_metrics.mae,
        "beats_last_7_day_avg_overall": beats_7,
        "beats_last_14_day_avg_overall": beats_14,
        "beats_baseline_overall": beats_7,
        "dins_beating_last_7_day_avg": beats_7_count,
        "dins_beating_last_14_day_avg": beats_14_count,
    }


def _build_summary(
    global_metrics: dict[str, Any],
    forecast_rows: pd.DataFrame,
    anomalies: pd.DataFrame,
    config: BacktestRunConfig,
    started_at: datetime,
    run_id: str,
) -> dict[str, Any]:
    anomaly_count = int(len(anomalies))
    total_rows = int(len(forecast_rows))
    anomaly_pct = float(anomaly_count / total_rows) if total_rows else None
    return {
        "run_id": run_id,
        "backtest_name": config.backtest_name,
        "model_version": config.model_version,
        "train_path": str(config.train_path),
        "actual_path": str(config.actual_path),
        "outdir": str(config.outdir),
        "forecast_horizon": config.forecast_horizon,
        "total_rows": total_rows,
        "din_count": int(forecast_rows["din"].nunique()) if total_rows else 0,
        "forecast_date_count": int(forecast_rows["forecast_date"].nunique()) if total_rows else 0,
        "anomaly_count": anomaly_count,
        "anomaly_percentage": anomaly_pct,
        "model_beats_last_7_day_avg_overall": global_metrics.get("beats_last_7_day_avg_overall"),
        "model_beats_last_14_day_avg_overall": global_metrics.get("beats_last_14_day_avg_overall"),
        "model_beats_last_7_day_avg_per_din_count": global_metrics.get("dins_beating_last_7_day_avg"),
        "model_beats_last_14_day_avg_per_din_count": global_metrics.get("dins_beating_last_14_day_avg"),
        "report_generated_at": started_at.isoformat(),
    }


def _file_hash(path: Path) -> str:
    digest = sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
