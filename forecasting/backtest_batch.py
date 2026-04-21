from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from forecasting.backtest_core import BacktestRunConfig, BacktestRunner
from forecasting.data import aggregate_weekly, load_input_csv
from forecasting.metrics import compute_regression_metrics
from forecasting.reporting import ensure_output_dir, write_dataframe_artifacts, write_json_artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run rolling-origin PharmaForecast backtests.")
    parser.add_argument("--fixtures-dir", required=True, type=Path, help="Directory with *_train.csv and *_actual.csv.")
    parser.add_argument("--model-version", required=True, help="Model version label.")
    parser.add_argument("--outdir", required=True, type=Path, help="Output directory for aggregated artifacts.")
    parser.add_argument(
        "--stock-levels",
        type=Path,
        default=None,
        help="Optional CSV with din,quantity_on_hand for stockout risk evaluation.",
    )
    parser.add_argument(
        "--minimum-history-points",
        type=int,
        default=8,
        help="Minimum history threshold used for anomaly detection.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    runner = BacktestRunner()
    fixtures_dir = args.fixtures_dir
    output_dir = ensure_output_dir(args.outdir)

    train_files = sorted(fixtures_dir.glob("*_train.csv"))
    if not train_files:
        raise SystemExit(f"no train fixtures found in {fixtures_dir}")

    step_results = []
    for train_path in train_files:
        actual_path = train_path.with_name(train_path.name.replace("_train.csv", "_actual.csv"))
        if not actual_path.is_file():
            raise SystemExit(f"missing actual file for {train_path.name}")

        step_name = train_path.stem.replace("_train", "")
        step_dir = output_dir / step_name

        actual_frame = load_input_csv(actual_path)
        config = BacktestRunConfig(
            train_path=train_path,
            actual_path=actual_path,
            backtest_name=step_name,
            model_version=args.model_version,
            outdir=step_dir,
            forecast_horizon=int(aggregate_weekly(actual_frame)["dispensed_date"].nunique()),
            stock_levels_path=args.stock_levels,
            minimum_history_points=args.minimum_history_points,
        )
        result = runner.run(config)
        step_results.append(result)

    combined_forecast_rows = pd.concat([result.forecast_rows for result in step_results], ignore_index=True)
    combined_din_metrics = pd.concat([result.din_metrics for result in step_results], ignore_index=True)
    anomaly_frames = [result.anomalies for result in step_results if not result.anomalies.empty]
    combined_anomalies = pd.concat(anomaly_frames, ignore_index=True) if anomaly_frames else pd.DataFrame()
    rows_evaluated = int(len(combined_forecast_rows))
    baseline_7_mae = _weighted_average(
        [result.global_metrics.get("baseline_last_7_day_avg_mae") for result in step_results],
        [result.global_metrics.get("rows_evaluated") for result in step_results],
    )
    baseline_14_mae = _weighted_average(
        [result.global_metrics.get("baseline_last_14_day_avg_mae") for result in step_results],
        [result.global_metrics.get("rows_evaluated") for result in step_results],
    )
    model_metrics = compute_regression_metrics(
        combined_forecast_rows["actual_quantity"],
        combined_forecast_rows["yhat"],
        combined_forecast_rows["yhat_lower"],
        combined_forecast_rows["yhat_upper"],
    )
    global_metrics = {
        "run_name": fixtures_dir.name,
        "model_version": args.model_version,
        "rows_evaluated": rows_evaluated,
        "din_count": int(combined_forecast_rows["din"].nunique()) if rows_evaluated else 0,
        "forecast_date_count": int(combined_forecast_rows["forecast_date"].nunique()) if rows_evaluated else 0,
        "mae": model_metrics.mae,
        "rmse": model_metrics.rmse,
        "wape": model_metrics.wape,
        "mape": model_metrics.mape,
        "bias": model_metrics.bias,
        "interval_coverage": model_metrics.interval_coverage,
        "direction_accuracy": _weighted_average(
            [result.global_metrics.get("direction_accuracy") for result in step_results],
            [result.global_metrics.get("rows_evaluated") for result in step_results],
        ),
        "stockout_risk_proxy": _weighted_average(
            [result.global_metrics.get("stockout_risk_proxy") for result in step_results],
            [result.global_metrics.get("rows_evaluated") for result in step_results],
        ),
        "overforecast_units": float(sum(result.global_metrics.get("overforecast_units") or 0.0 for result in step_results)),
        "underforecast_units": float(sum(result.global_metrics.get("underforecast_units") or 0.0 for result in step_results)),
        "baseline_last_7_day_avg_mae": baseline_7_mae,
        "baseline_last_14_day_avg_mae": baseline_14_mae,
        "beats_last_7_day_avg_overall": _better_than(model_metrics.mae, baseline_7_mae),
        "beats_last_14_day_avg_overall": _better_than(model_metrics.mae, baseline_14_mae),
        "beats_baseline_overall": _better_than(model_metrics.mae, baseline_7_mae),
        "dins_beating_last_7_day_avg": int(
            sum(result.global_metrics.get("dins_beating_last_7_day_avg") or 0 for result in step_results)
        ),
        "dins_beating_last_14_day_avg": int(
            sum(result.global_metrics.get("dins_beating_last_14_day_avg") or 0 for result in step_results)
        ),
        "step_count": len(step_results),
    }
    aggregate_summary = {
        "run_name": fixtures_dir.name,
        "model_version": args.model_version,
        "step_count": len(step_results),
        "total_rows": rows_evaluated,
        "anomaly_count": int(len(combined_anomalies)),
        "anomaly_percentage": float(len(combined_anomalies) / rows_evaluated) if rows_evaluated else None,
        "step_names": [result.config.backtest_name for result in step_results],
        "step_summaries": [result.summary for result in step_results],
        "model_beats_last_7_day_avg_overall": global_metrics["beats_last_7_day_avg_overall"],
        "model_beats_last_14_day_avg_overall": global_metrics["beats_last_14_day_avg_overall"],
        "model_beats_last_7_day_avg_per_din_count": global_metrics["dins_beating_last_7_day_avg"],
        "model_beats_last_14_day_avg_per_din_count": global_metrics["dins_beating_last_14_day_avg"],
    }

    write_dataframe_artifacts(
        combined_forecast_rows,
        output_dir / "forecast_rows.csv",
        output_dir / "forecast_rows.json",
    )
    write_dataframe_artifacts(combined_din_metrics, output_dir / "din_metrics.csv")
    write_json_artifact(global_metrics, output_dir / "global_metrics.json")
    write_dataframe_artifacts(combined_anomalies, output_dir / "anomalies.csv")
    write_dataframe_artifacts(pd.DataFrame([aggregate_summary]), output_dir / "backtest_summary.csv")
    write_json_artifact(aggregate_summary, output_dir / "backtest_summary.json")

    return 0


def _weighted_average(values: list[float | None], weights: list[float | None]) -> float | None:
    filtered = [
        (float(value), float(weight))
        for value, weight in zip(values, weights)
        if value is not None and weight is not None and float(weight) > 0
    ]
    if not filtered:
        return None
    numerator = sum(value * weight for value, weight in filtered)
    denominator = sum(weight for _value, weight in filtered)
    return float(numerator / denominator) if denominator else None


def _better_than(model_mae: float | None, baseline_mae: float | None) -> bool | None:
    if model_mae is None or baseline_mae is None:
        return None
    return model_mae < baseline_mae


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
