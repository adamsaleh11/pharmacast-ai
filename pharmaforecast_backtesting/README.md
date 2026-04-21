# PharmaForecast Backtesting Fixtures

These CSVs were generated from `pharmaforecast_test_dispensing_v2.csv` for repeatable backtesting.

## Files
- `test_01_next_1_period_train.csv` + `test_01_next_1_period_actual.csv`
  - Train on all dates through 2026-04-06
  - Forecast 1 next period: 2026-04-13

- `test_02_next_2_periods_train.csv` + `test_02_next_2_periods_actual.csv`
  - Train on all dates through 2026-03-30
  - Forecast next 2 periods: 2026-04-06 to 2026-04-13

- `test_03_next_4_periods_train.csv` + `test_03_next_4_periods_actual.csv`
  - Train on all dates through 2026-03-16
  - Forecast next 4 periods: 2026-03-23 to 2026-04-13

- `rolling_origin/step_*`
  - Walk-forward backtests.
  - Start with 8 historical periods, then forecast 1 next period at a time.

## How to use
For each test:
1. Feed only the `*_train.csv` file into the forecasting pipeline.
2. Ask the model to forecast the same horizon and dates covered by the matching `*_actual.csv`.
3. Compare predicted vs actual by `din` and `dispensed_date`.
4. Log MAE, RMSE, WAPE, bias, and interval coverage.

## CLI
Single backtest:

```bash
python -m forecasting.backtest \
  --train pharmaforecast_backtesting/test_01_next_1_period_train.csv \
  --actual pharmaforecast_backtesting/test_01_next_1_period_actual.csv \
  --name test_01_next_1_period \
  --model-version prophet_v1 \
  --forecast-horizon 1 \
  --outdir ./artifacts/backtests/test_01
```

Rolling-origin batch:

```bash
python -m forecasting.backtest_batch \
  --fixtures-dir ./pharmaforecast_backtesting/rolling_origin \
  --model-version prophet_v1 \
  --outdir ./artifacts/backtests/rolling_origin
```

## Output structure
Each run writes:

```text
artifacts/backtests/<run_name>/
  forecast_rows.csv
  forecast_rows.json
  din_metrics.csv
  global_metrics.json
  anomalies.csv
  backtest_summary.csv
  backtest_summary.json
```

Rolling-origin batch runs also preserve per-step subdirectories under the batch output folder.

## Important
Do not leak the `*_actual.csv` rows into training.
