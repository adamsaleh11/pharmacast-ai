from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from forecasting.backtest_core import BacktestRunConfig, BacktestRunner
from forecasting.data import load_input_csv, validate_input_frame
from forecasting.exceptions import BacktestSchemaError
from forecasting.metrics import compute_direction_accuracy, compute_regression_metrics


class _FakeForecastGenerator:
    def __init__(self) -> None:
        self.received_history_frames: list[pd.DataFrame] = []

    def forecast(self, train_rows: pd.DataFrame, horizon_length: int) -> pd.DataFrame:
        self.received_history_frames.append(train_rows.copy())
        history = train_rows.sort_values("dispensed_date")
        last_value = float(history["quantity_dispensed"].iloc[-1])
        last_date = pd.to_datetime(history["dispensed_date"].iloc[-1])
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=7), periods=horizon_length, freq="W-MON")
        return pd.DataFrame(
            {
                "forecast_date": [ts.date() for ts in future_dates],
                "yhat": [last_value for _ in range(horizon_length)],
                "yhat_lower": [max(0.0, last_value - 1.0) for _ in range(horizon_length)],
                "yhat_upper": [last_value + 1.0 for _ in range(horizon_length)],
            }
        )


def _write_csv(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


def test_schema_validation_accepts_optional_columns(tmp_path):
    csv_path = _write_csv(
        tmp_path / "fixture.csv",
        "dispensed_date,din,quantity_dispensed,cost_per_unit\n2026-04-06,12345678,10,1.50\n",
    )

    frame = load_input_csv(csv_path)

    assert list(frame.columns)[:3] == ["dispensed_date", "din", "quantity_dispensed"]
    assert frame.iloc[0]["din"] == "12345678"


def test_schema_validation_rejects_missing_required_column():
    frame = pd.DataFrame([{"dispensed_date": "2026-04-06", "din": "12345678"}])

    try:
        validate_input_frame(frame)
    except BacktestSchemaError as exc:
        assert "missing_required_columns" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected schema validation failure")


def test_metrics_compute_safe_mape_and_direction_accuracy():
    summary = compute_regression_metrics([10, 0, 20], [8, 2, 24], [7, 1, 20], [11, 3, 30])
    assert summary.mae == 8 / 3
    assert summary.rmse == pytest.approx(2.8284271247)
    assert summary.wape == pytest.approx(8 / 30)
    assert summary.mape == 0.2
    assert summary.bias == pytest.approx(4 / 30)
    assert summary.interval_coverage == pytest.approx(2 / 3)

    actual = pd.Series([12, 9, 9])
    predicted = pd.Series([13, 8, 9])
    previous_actual = pd.Series([10, 12, 9])
    assert compute_direction_accuracy(actual, predicted, previous_actual) == 1.0


def test_backtest_runner_uses_train_only_and_saves_artifacts(tmp_path):
    train_csv = _write_csv(
        tmp_path / "train.csv",
        "\n".join(
            [
                "dispensed_date,din,quantity_dispensed,cost_per_unit",
                "2026-03-23,11111111,10,1.0",
                "2026-03-30,11111111,12,1.0",
                "2026-03-23,22222222,20,2.0",
                "2026-03-30,22222222,22,2.0",
            ]
        )
        + "\n",
    )
    actual_csv = _write_csv(
        tmp_path / "actual.csv",
        "\n".join(
            [
                "dispensed_date,din,quantity_dispensed,cost_per_unit",
                "2026-04-06,11111111,13,1.0",
                "2026-04-06,22222222,25,2.0",
            ]
        )
        + "\n",
    )

    forecaster = _FakeForecastGenerator()
    runner = BacktestRunner(forecaster=forecaster)
    result = runner.run(
        BacktestRunConfig(
            train_path=train_csv,
            actual_path=actual_csv,
            backtest_name="test_single",
            model_version="prophet_v1",
            outdir=tmp_path / "artifacts",
            forecast_horizon=1,
        )
    )

    assert all(
        frame["dispensed_date"].astype(str).max() <= "2026-03-30"
        for frame in forecaster.received_history_frames
    )
    assert (tmp_path / "artifacts" / "forecast_rows.csv").is_file()
    assert (tmp_path / "artifacts" / "forecast_rows.json").is_file()
    assert (tmp_path / "artifacts" / "din_metrics.csv").is_file()
    assert (tmp_path / "artifacts" / "global_metrics.json").is_file()
    assert (tmp_path / "artifacts" / "anomalies.csv").is_file()
    assert (tmp_path / "artifacts" / "backtest_summary.csv").is_file()
    assert (tmp_path / "artifacts" / "backtest_summary.json").is_file()
    assert len(result.forecast_rows) == 2
    assert set(result.forecast_rows["anomaly_flag"]) <= {True, False}
    assert result.summary["anomaly_count"] >= 0


def test_backtest_default_forecaster_beats_baselines_on_short_weekly_fixture(tmp_path):
    runner = BacktestRunner()

    result = runner.run(
        BacktestRunConfig(
            train_path=Path("pharmaforecast_backtesting/test_01_next_1_period_train.csv"),
            actual_path=Path("pharmaforecast_backtesting/test_01_next_1_period_actual.csv"),
            backtest_name="test_01_next_1_period",
            model_version="prophet_v1",
            outdir=tmp_path / "artifacts",
            forecast_horizon=1,
        )
    )

    assert result.global_metrics["mae"] < result.global_metrics["baseline_last_7_day_avg_mae"]
    assert result.global_metrics["mae"] < result.global_metrics["baseline_last_14_day_avg_mae"]
    assert result.global_metrics["interval_coverage"] == 1.0
    assert result.summary["anomaly_count"] == 0
    assert (result.forecast_rows["yhat"] >= 0).all()
