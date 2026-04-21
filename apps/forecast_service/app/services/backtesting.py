from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd

from apps.forecast_service.app.schemas.backtest import BacktestUploadRequest
from forecasting.backtest_core import BacktestRunConfig, BacktestRunner
from forecasting.data import aggregate_weekly, normalize_input_frame, validate_input_frame
from forecasting.metrics import compute_regression_metrics


MIN_TRAINING_PERIODS = 8
MAX_ROLLING_ORIGIN_STEPS = 12
PASS_WAPE_THRESHOLD = 0.20
LOW_CONFIDENCE_WAPE_THRESHOLD = 0.35
MIN_INTERVAL_COVERAGE = 0.75


def run_uploaded_backtest(request: BacktestUploadRequest) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        frame = _request_rows_frame(request)
        preprocessing = _preprocessing_summary(request, frame)
        result = _run_rolling_origin(frame, request, preprocessing)
        return _summary_payload(result, request.model_version, generated_at)
    except ValueError as exc:
        if str(exc) == "insufficient_backtest_history":
            frame = _request_rows_frame(request)
            preprocessing = _preprocessing_summary(request, frame)
            din_count = len({row.din for row in request.rows})
            return _failure_payload(
                request.model_version,
                generated_at,
                error_message="insufficient_backtest_history",
                rows_evaluated=0,
                din_count=din_count,
                preprocessing=preprocessing,
            )
        return _error_payload(request.model_version, generated_at, str(exc))
    except Exception as exc:
        return _error_payload(request.model_version, generated_at, str(exc))


def _request_rows_frame(request: BacktestUploadRequest) -> pd.DataFrame:
    rows = [row.model_dump() for row in request.rows]
    frame = pd.DataFrame(rows)
    validate_input_frame(frame)
    return normalize_input_frame(frame)


def _preprocessing_summary(request: BacktestUploadRequest, frame: pd.DataFrame) -> dict[str, Any]:
    weekly = aggregate_weekly(frame)
    dates = sorted(pd.to_datetime(weekly["dispensed_date"]).dt.date.unique().tolist())
    return {
        "raw_rows_received": len(request.rows),
        "usable_rows": int(len(weekly)),
        "min_required_rows": MIN_TRAINING_PERIODS,
        "date_range": {
            "start": dates[0].isoformat() if dates else None,
            "end": dates[-1].isoformat() if dates else None,
        },
    }


def _run_rolling_origin(
    frame: pd.DataFrame,
    request: BacktestUploadRequest,
    preprocessing: dict[str, Any],
) -> dict[str, Any]:
    weekly = aggregate_weekly(frame)
    forecast_dates = _eligible_forecast_dates(weekly)
    if not forecast_dates:
        raise ValueError("insufficient_backtest_history")

    step_results = []
    artifact_root = _artifact_root(request)
    temp_context = None
    if artifact_root is None:
        temp_context = TemporaryDirectory()
        artifact_root = Path(temp_context.name)

    try:
        for index, forecast_date in enumerate(forecast_dates, start=1):
            train = weekly.loc[pd.to_datetime(weekly["dispensed_date"]).dt.date < forecast_date].copy()
            actual = weekly.loc[pd.to_datetime(weekly["dispensed_date"]).dt.date == forecast_date].copy()
            step_name = f"step_{index:02d}"
            step_dir = artifact_root / step_name
            train_path = step_dir / "train.csv"
            actual_path = step_dir / "actual.csv"
            step_dir.mkdir(parents=True, exist_ok=True)
            train.to_csv(train_path, index=False)
            actual.to_csv(actual_path, index=False)
            step_results.append(
                BacktestRunner().run(
                    BacktestRunConfig(
                        train_path=train_path,
                        actual_path=actual_path,
                        backtest_name=step_name,
                        model_version=request.model_version,
                        outdir=step_dir,
                        forecast_horizon=1,
                    )
                )
            )
    finally:
        if temp_context is not None:
            temp_context.cleanup()

    combined_forecast_rows = pd.concat([result.forecast_rows for result in step_results], ignore_index=True)
    anomaly_count = int(sum(len(result.anomalies) for result in step_results))
    model_metrics = compute_regression_metrics(
        combined_forecast_rows["actual_quantity"],
        combined_forecast_rows["yhat"],
        combined_forecast_rows["yhat_lower"],
        combined_forecast_rows["yhat_upper"],
    )
    baseline_last_7_day_avg_mae = _weighted_average(
        [result.global_metrics.get("baseline_last_7_day_avg_mae") for result in step_results],
        [result.global_metrics.get("rows_evaluated") for result in step_results],
    )
    baseline_last_14_day_avg_mae = _weighted_average(
        [result.global_metrics.get("baseline_last_14_day_avg_mae") for result in step_results],
        [result.global_metrics.get("rows_evaluated") for result in step_results],
    )
    return {
        "mae": model_metrics.mae,
        "wape": model_metrics.wape,
        "interval_coverage": model_metrics.interval_coverage,
        "anomaly_count": anomaly_count,
        "beats_last_7_day_avg": _better_than(model_metrics.mae, baseline_last_7_day_avg_mae),
        "beats_last_14_day_avg": _better_than(model_metrics.mae, baseline_last_14_day_avg_mae),
        "baseline_last_7_day_avg_mae": baseline_last_7_day_avg_mae,
        "baseline_last_14_day_avg_mae": baseline_last_14_day_avg_mae,
        "rows_evaluated": int(len(combined_forecast_rows)),
        "raw_rows_received": preprocessing["raw_rows_received"],
        "usable_rows": preprocessing["usable_rows"],
        "min_required_rows": preprocessing["min_required_rows"],
        "date_range": preprocessing["date_range"],
        "model_path_counts": _model_path_counts(combined_forecast_rows),
        "din_count": int(combined_forecast_rows["din"].nunique()) if not combined_forecast_rows.empty else 0,
        "artifact_path": str(artifact_root) if request.debug_artifacts else None,
    }


def _eligible_forecast_dates(weekly: pd.DataFrame) -> list[Any]:
    dates = sorted(pd.to_datetime(weekly["dispensed_date"]).dt.date.unique().tolist())
    eligible = []
    for forecast_date in dates:
        history = weekly.loc[pd.to_datetime(weekly["dispensed_date"]).dt.date < forecast_date]
        if history.empty:
            continue
        min_history = int(history.groupby("din")["dispensed_date"].count().min())
        if min_history >= MIN_TRAINING_PERIODS:
            eligible.append(forecast_date)
    return eligible[-MAX_ROLLING_ORIGIN_STEPS:]


def _artifact_root(request: BacktestUploadRequest) -> Path | None:
    if not request.debug_artifacts:
        return None
    return Path("artifacts") / "backtests" / "debug" / request.csv_upload_id


def _summary_payload(result: dict[str, Any], model_version: str, generated_at: str) -> dict[str, Any]:
    status = _status_for(result)
    payload = {
        "status": status,
        "model_version": model_version,
        "mae": result["mae"],
        "wape": result["wape"],
        "interval_coverage": result["interval_coverage"],
        "anomaly_count": result["anomaly_count"],
        "beats_last_7_day_avg": result["beats_last_7_day_avg"],
        "beats_last_14_day_avg": result["beats_last_14_day_avg"],
        "baseline_last_7_day_avg_mae": result["baseline_last_7_day_avg_mae"],
        "baseline_last_14_day_avg_mae": result["baseline_last_14_day_avg_mae"],
        "rows_evaluated": result["rows_evaluated"],
        "raw_rows_received": result["raw_rows_received"],
        "usable_rows": result["usable_rows"],
        "min_required_rows": result["min_required_rows"],
        "date_range": result["date_range"],
        "ready_for_forecast": status == "PASS",
        "model_path_counts": result["model_path_counts"],
        "din_count": result["din_count"],
        "generated_at": generated_at,
        "error_message": None,
        "artifact_path": result["artifact_path"],
    }
    return payload


def _failure_payload(
    model_version: str,
    generated_at: str,
    *,
    error_message: str,
    rows_evaluated: int,
    din_count: int,
    preprocessing: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "FAIL",
        "model_version": model_version,
        "mae": None,
        "wape": None,
        "interval_coverage": None,
        "anomaly_count": None,
        "beats_last_7_day_avg": None,
        "beats_last_14_day_avg": None,
        "baseline_last_7_day_avg_mae": None,
        "baseline_last_14_day_avg_mae": None,
        "rows_evaluated": rows_evaluated,
        "raw_rows_received": preprocessing["raw_rows_received"],
        "usable_rows": preprocessing["usable_rows"],
        "min_required_rows": preprocessing["min_required_rows"],
        "date_range": preprocessing["date_range"],
        "ready_for_forecast": False,
        "model_path_counts": {},
        "din_count": din_count,
        "generated_at": generated_at,
        "error_message": error_message,
        "artifact_path": None,
    }


def _error_payload(model_version: str, generated_at: str, error_message: str) -> dict[str, Any]:
    return {
        "status": "ERROR",
        "model_version": model_version,
        "mae": None,
        "wape": None,
        "interval_coverage": None,
        "anomaly_count": None,
        "beats_last_7_day_avg": None,
        "beats_last_14_day_avg": None,
        "baseline_last_7_day_avg_mae": None,
        "baseline_last_14_day_avg_mae": None,
        "rows_evaluated": None,
        "raw_rows_received": None,
        "usable_rows": None,
        "min_required_rows": MIN_TRAINING_PERIODS,
        "date_range": None,
        "ready_for_forecast": False,
        "model_path_counts": {},
        "din_count": None,
        "generated_at": generated_at,
        "error_message": error_message,
        "artifact_path": None,
    }


def _status_for(result: dict[str, Any]) -> str:
    if result["anomaly_count"] > 0:
        return "FAIL"
    beats_all_baselines = result["beats_last_7_day_avg"] and result["beats_last_14_day_avg"]
    if (
        beats_all_baselines
        and result["wape"] is not None
        and result["wape"] <= PASS_WAPE_THRESHOLD
        and result["interval_coverage"] is not None
        and result["interval_coverage"] >= MIN_INTERVAL_COVERAGE
    ):
        return "PASS"
    if result["wape"] is not None and result["wape"] <= LOW_CONFIDENCE_WAPE_THRESHOLD:
        return "LOW_CONFIDENCE"
    return "FAIL"


def _weighted_average(values: list[float | None], weights: list[float | None]) -> float | None:
    filtered = [
        (float(value), float(weight))
        for value, weight in zip(values, weights)
        if value is not None and weight is not None and float(weight) > 0
    ]
    if not filtered:
        return None
    total_weight = sum(weight for _value, weight in filtered)
    return float(sum(value * weight for value, weight in filtered) / total_weight) if total_weight else None


def _better_than(model_mae: float | None, baseline_mae: float | None) -> bool | None:
    if model_mae is None or baseline_mae is None:
        return None
    return model_mae < baseline_mae


def _model_path_counts(forecast_rows: pd.DataFrame) -> dict[str, int]:
    if "model_path" not in forecast_rows:
        return {}
    return {str(key): int(value) for key, value in forecast_rows["model_path"].value_counts().sort_index().items()}
