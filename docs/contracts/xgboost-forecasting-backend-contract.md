# Implementation Handoff Contract

## 1. Summary

- Implemented `xgboost_residual_v1` as the default Python forecast-service model path for numeric drug demand forecasting.
- Implemented a recursive weekly XGBoost model with lag features, rolling statistics, calendar features, conservative CPU `hist` tree settings, and residual-calibrated prediction intervals.
- Kept Prophet code available as a comparison/fallback implementation, but the default production forecast engine and default backtest runner now use XGBoost.
- Exposed the model used for single-drug forecasts through `model_path` in `POST /forecast/drug` responses so Spring Boot can store and display it in drug panel details.
- Exposed upload backtest model usage through `model_version` and `model_path_counts` in `POST /backtest/upload` responses so Spring Boot can store and display it in upload history.
- Tightened upload backtest readiness: `PASS` now requires beating both baseline MAEs, meeting WAPE threshold, meeting interval coverage threshold, and having zero anomalies.
- Why it was implemented: prior Prophet evidence did not consistently beat simple baselines, so it was not strong enough for inventory/reorder trust. The XGBoost residual model passed the upload-style rolling-origin fixture.
- In scope: Python forecast service model runner, backtest runner default, public forecast model metadata, upload backtest model metadata, dependencies, and tests.
- Out of scope: Spring Boot persistence changes, frontend drug panel UI, frontend upload history UI, database migrations for model metadata, model registry service, persisted trained model artifacts, scheduled retraining, and tenant authorization in Python.
- Owner: Python forecast service under `apps.forecast_service`; Spring Boot owns persistence, tenancy enforcement, and UI-facing API aggregation.

## 2. Files Added or Changed

- `apps/forecast_service/app/services/model.py`: updated. Added `XGBoostModelRunner`, XGBoost feature engineering, recursive point forecasting, residual interval calibration, model path constants, and XGBoost fallback behavior.
- `apps/forecast_service/app/services/forecasting.py`: updated. Default forecast engine now uses `XGBoostModelRunner`; `FORECAST_CODE_PATH` is now `weekly-xgboost-residual-v1`; internal `ForecastResult` includes `model_path`.
- `apps/forecast_service/app/api/forecasts.py`: updated. `POST /forecast/drug` public response now includes `model_path`.
- `apps/forecast_service/app/services/backtesting.py`: updated. Upload backtest summary includes `model_path_counts`; `PASS` status now requires beating both simple baselines.
- `apps/forecast_service/app/schemas/backtest.py`: updated. Default `BacktestUploadRequest.model_version` is now `xgboost_residual_v1`; `BacktestUploadSummary` includes `model_path_counts`.
- `apps/forecast_service/app/services/domain.py`: updated before this contract. `ForecastPrediction` and `ForecastResult` carry `model_path`.
- `forecasting/model.py`: updated. Added `XGBoostForecastGenerator` for CLI/backtest parity with production XGBoost behavior; Prophet generator remains available.
- `forecasting/backtest_core.py`: updated. Default `BacktestRunner` now uses `XGBoostForecastGenerator`; forecast artifacts and global metrics carry `model_path`.
- `requirements.txt`: updated. Added `xgboost>=2.0,<4.0`.
- `pyproject.toml`: updated. Added `xgboost>=2.0,<4.0`.
- `tests/forecast_service/test_drug_forecast.py`: updated. Verifies forecast response header, model metadata, Prophet fallback, and XGBoost non-negative interval behavior.
- `tests/forecast_service/test_spring_forecast_contract.py`: updated. Verifies Spring-facing `POST /forecast/drug` response includes `model_path` and excludes `patient_id`.
- `tests/forecast_service/test_backtest_upload.py`: updated. Verifies upload backtest returns `PASS`, beats both baselines, includes `model_path_counts`, and rejects `patient_id`.
- `tests/forecasting/test_backtest.py`: updated. Verifies default backtest forecaster uses `xgboost_residual_interval`.
- `tests/forecast_service/test_foundation_structure.py`: updated. Verifies both Prophet and XGBoost dependencies are declared.
- `docs/contracts/xgboost-forecasting-backend-contract.md`: created. This backend handoff contract.

## 3. Public Interface Contract

### `POST /forecast/drug`

- Name: `POST /forecast/drug`
- Type: HTTP endpoint
- Purpose: Generate one numeric demand forecast for one DIN at one location.
- Owner: `apps.forecast_service.app.api.forecasts`
- Inputs: JSON body matching `DrugForecastRequest`
- Outputs: JSON forecast result on success; JSON error on validation/forecast failure
- Required fields:
  - `location_id: string`
  - `din: string`
  - `quantity_on_hand: integer >= 0`
- Optional fields:
  - `horizon_days: integer >= 1`, default `7`
  - `lead_time_days: integer >= 1`, default `2`
  - `safety_multiplier: number > 0`, default `1.0`
  - `red_threshold_days: integer >= 1`, default `3`
  - `amber_threshold_days: integer >= 1`, default `7`
  - `supplemental_history: array[SupplementalHistoryPoint] | null`, default `null`
- Validation rules:
  - `quantity_on_hand` is required and must be `0` or greater.
  - `supplemental_history[].week_start` also accepts inbound alias `week`.
  - `supplemental_history[].quantity` must be `0` or greater.
  - Forecast service rejects fewer than 14 raw dispensing rows with `insufficient_data`.
- Defaults:
  - Forecast engine default model runner is `XGBoostModelRunner`.
  - Response header `X-Forecast-Code-Path` is `weekly-xgboost-residual-v1`.
- Status codes or result states:
  - `200 OK` when forecast succeeds.
  - `422` for insufficient data, invalid request, or invalid forecast output.
  - `503` for forecast timeout.
- Success output fields:
  - `din: string`
  - `location_id: string`
  - `horizon_days: integer`
  - `predicted_quantity: integer`
  - `prophet_lower: integer`
  - `prophet_upper: integer`
  - `confidence: "HIGH" | "MEDIUM" | "LOW"`
  - `days_of_supply: number`
  - `avg_daily_demand: number`
  - `reorder_status: "GREEN" | "AMBER" | "RED"`
  - `reorder_point: number`
  - `generated_at: ISO-8601 timestamp string`
  - `data_points_used: integer`
  - `model_path: string`
- Error shapes:
  - Insufficient history:
    ```json
    {
      "error": "insufficient_data",
      "minimum_rows": 14,
      "confidence": "LOW"
    }
    ```
  - Forecast timeout:
    ```json
    {
      "error": "forecast_timeout",
      "confidence": "LOW"
    }
    ```
  - Invalid forecast output:
    ```json
    {
      "error": "invalid_forecast_output",
      "confidence": "LOW",
      "details": "prophet_lower must be less than or equal to prophet_upper and both must be non-negative"
    }
    ```
- Example input:
  ```json
  {
    "location_id": "b098e4c4-e499-45d0-aadc-86edfdac555b",
    "din": "02230711",
    "horizon_days": 21,
    "quantity_on_hand": 80,
    "lead_time_days": 2,
    "safety_multiplier": 1.25,
    "red_threshold_days": 3,
    "amber_threshold_days": 7,
    "supplemental_history": [
      {
        "week_start": "2026-04-13",
        "quantity": 5
      }
    ]
  }
  ```
- Example output:
  ```json
  {
    "din": "02230711",
    "location_id": "b098e4c4-e499-45d0-aadc-86edfdac555b",
    "horizon_days": 21,
    "predicted_quantity": 42,
    "prophet_lower": 38,
    "prophet_upper": 47,
    "confidence": "HIGH",
    "days_of_supply": 10.5,
    "avg_daily_demand": 6.0,
    "reorder_status": "GREEN",
    "reorder_point": 18.0,
    "generated_at": "2026-04-21T19:03:23Z",
    "data_points_used": 21,
    "model_path": "xgboost_residual_interval"
  }
  ```

### `POST /forecast/batch`

- Name: `POST /forecast/batch`
- Type: HTTP endpoint returning Server-Sent Events
- Purpose: Generate numeric forecasts for multiple DINs at one location.
- Owner: `apps.forecast_service.app.api.forecasts`
- Inputs: JSON body matching `BatchForecastRequest`
- Outputs: SSE events containing per-DIN complete/error events and a final done event
- Required fields:
  - `location_id: string`
  - `dins: array[string]` with at least one item
  - `horizon_days: 7 | 14 | 30`
  - `thresholds: object` keyed by DIN
- Optional fields inside `thresholds[din]`:
  - `lead_time_days: integer >= 1`, default `2`
  - `safety_multiplier: 1.5 | 1.0 | 0.75`, default `1.0`
  - `red_threshold_days: integer >= 1`, default `3`
  - `amber_threshold_days: integer >= 1`, default `7`
- Validation rules:
  - `dins` must not be empty.
  - `horizon_days` must be exactly `7`, `14`, or `30`.
  - `safety_multiplier` accepts only `1.5`, `1.0`, or `0.75`.
- Defaults:
  - Response header `X-Forecast-Code-Path` is `weekly-xgboost-residual-v1`.
  - Missing threshold for a DIN uses lead time `2`, safety multiplier `1.0`, red threshold `3`, amber threshold `7`.
- Status codes or result states:
  - HTTP status `200 OK` for stream creation.
  - Per-DIN event status is `"complete"` or `"error"`.
  - Final event status is `"done"`.
- Error shapes:
  - Per-DIN structured errors use:
    ```json
    {
      "din": "11111111",
      "status": "error",
      "error": "insufficient_data"
    }
    ```
- Example input:
  ```json
  {
    "location_id": "11111111-1111-1111-1111-111111111111",
    "dins": ["11111111", "22222222"],
    "horizon_days": 7,
    "thresholds": {
      "11111111": {
        "lead_time_days": 2,
        "safety_multiplier": 1.0
      }
    }
  }
  ```
- Example output event:
  ```text
  data: {"din":"11111111","status":"complete","result":{"din":"11111111","location_id":"11111111-1111-1111-1111-111111111111","horizon_days":7,"predicted_quantity":10,"prophet_lower":8,"prophet_upper":12,"confidence":"HIGH","model_path":"xgboost_residual_interval","days_of_supply":0.0,"avg_daily_demand":1.4,"reorder_status":"RED","reorder_point":2.8,"generated_at":"2026-04-21T20:00:00+00:00","data_points_used":30}}
  ```

### `POST /backtest/upload`

- Name: `POST /backtest/upload`
- Type: HTTP endpoint
- Purpose: Run upload-style rolling-origin backtest for a candidate CSV upload.
- Owner: `apps.forecast_service.app.api.backtests`
- Inputs: JSON body matching `BacktestUploadRequest`
- Outputs: JSON body matching `BacktestUploadSummary`
- Required fields:
  - `organization_id: string`
  - `location_id: string`
  - `csv_upload_id: string`
  - `rows: array[BacktestDemandRow]` with at least one row
- Optional fields:
  - `model_version: string`, default `xgboost_residual_v1`
  - `debug_artifacts: boolean`, default `false`
  - `rows[].cost_per_unit: number | null`, default `null`
- Validation rules:
  - Request model forbids extra fields.
  - `rows[].dispensed_date` is required.
  - `rows[].din` is required.
  - `rows[].quantity_dispensed` is required and must be `0` or greater.
  - `patient_id` is forbidden because `BacktestDemandRow` uses `extra="forbid"`.
- Defaults:
  - `model_version` defaults to `xgboost_residual_v1`.
  - `debug_artifacts` defaults to `false`.
- Status codes or result states:
  - `200 OK` for `PASS`, `LOW_CONFIDENCE`, or `FAIL`.
  - `500` for `ERROR`.
  - `status` values: `"PASS" | "LOW_CONFIDENCE" | "FAIL" | "ERROR"`.
- Success output fields:
  - `status: "PASS" | "LOW_CONFIDENCE" | "FAIL" | "ERROR"`
  - `model_version: string`
  - `mae: number | null`
  - `wape: number | null`
  - `interval_coverage: number | null`
  - `anomaly_count: integer | null`
  - `beats_last_7_day_avg: boolean | null`
  - `beats_last_14_day_avg: boolean | null`
  - `baseline_last_7_day_avg_mae: number | null`
  - `baseline_last_14_day_avg_mae: number | null`
  - `rows_evaluated: integer | null`
  - `raw_rows_received: integer | null`
  - `usable_rows: integer | null`
  - `min_required_rows: integer | null`
  - `date_range: object | null`
  - `ready_for_forecast: boolean`
  - `model_path_counts: object<string, integer>`
  - `din_count: integer | null`
  - `generated_at: ISO-8601 timestamp string`
  - `error_message: string | null`
  - `artifact_path: string | null`
- Error shapes:
  - Insufficient backtest history returns `200 OK` with:
    ```json
    {
      "status": "FAIL",
      "model_version": "xgboost_residual_v1",
      "mae": null,
      "wape": null,
      "interval_coverage": null,
      "anomaly_count": null,
      "beats_last_7_day_avg": null,
      "beats_last_14_day_avg": null,
      "baseline_last_7_day_avg_mae": null,
      "baseline_last_14_day_avg_mae": null,
      "rows_evaluated": 0,
      "raw_rows_received": 2,
      "usable_rows": 2,
      "min_required_rows": 8,
      "date_range": {
        "start": "2026-01-05",
        "end": "2026-01-12"
      },
      "ready_for_forecast": false,
      "model_path_counts": {},
      "din_count": 1,
      "generated_at": "2026-04-21T20:00:00+00:00",
      "error_message": "insufficient_backtest_history",
      "artifact_path": null
    }
    ```
- Example input:
  ```json
  {
    "organization_id": "11111111-1111-1111-1111-111111111111",
    "location_id": "22222222-2222-2222-2222-222222222222",
    "csv_upload_id": "33333333-3333-3333-3333-333333333333",
    "model_version": "xgboost_residual_v1",
    "debug_artifacts": false,
    "rows": [
      {
        "dispensed_date": "2026-01-05",
        "din": "02431327",
        "quantity_dispensed": 54,
        "cost_per_unit": 0.55
      }
    ]
  }
  ```
- Example successful output:
  ```json
  {
    "status": "PASS",
    "model_version": "xgboost_residual_v1",
    "mae": 2.827777777777778,
    "wape": 0.0884832681442851,
    "interval_coverage": 0.7638888888888888,
    "anomaly_count": 0,
    "beats_last_7_day_avg": true,
    "beats_last_14_day_avg": true,
    "baseline_last_7_day_avg_mae": 3.0972222222222223,
    "baseline_last_14_day_avg_mae": 2.9097222222222223,
    "rows_evaluated": 72,
    "raw_rows_received": 336,
    "usable_rows": 336,
    "min_required_rows": 8,
    "date_range": {
      "start": "2025-04-07",
      "end": "2026-04-27"
    },
    "ready_for_forecast": true,
    "model_path_counts": {
      "xgboost_residual_interval": 72
    },
    "din_count": 6,
    "generated_at": "2026-04-21T20:00:15.125563+00:00",
    "error_message": null,
    "artifact_path": null
  }
  ```

## 4. Data Contract

### `DrugForecastRequest`

- Exact name: `DrugForecastRequest`
- Fields:
  - `location_id: str`
  - `din: str`
  - `horizon_days: int`
  - `quantity_on_hand: int`
  - `lead_time_days: int`
  - `safety_multiplier: float`
  - `red_threshold_days: int`
  - `amber_threshold_days: int`
  - `supplemental_history: Optional[list[SupplementalHistoryPoint]]`
- Required vs optional:
  - Required: `location_id`, `din`, `quantity_on_hand`
  - Optional/defaulted: `horizon_days`, `lead_time_days`, `safety_multiplier`, `red_threshold_days`, `amber_threshold_days`, `supplemental_history`
- Allowed values:
  - `quantity_on_hand >= 0`
  - `horizon_days >= 1`
  - `lead_time_days >= 1`
  - `safety_multiplier > 0`
  - `red_threshold_days >= 1`
  - `amber_threshold_days >= 1`
- Defaults:
  - `horizon_days=7`
  - `lead_time_days=2`
  - `safety_multiplier=1.0`
  - `red_threshold_days=3`
  - `amber_threshold_days=7`
  - `supplemental_history=None`
- Validation constraints: Pydantic validation plus custom API error for missing/negative `quantity_on_hand`.
- Migration notes: no database migration exists in Python. Spring Boot must add its own persistence field if forecasts table needs to store model metadata.
- Backward compatibility notes: success response now includes `model_path`, which is additive.

### `ForecastPrediction`

- Exact name: `ForecastPrediction`
- Fields:
  - `predicted_quantity: int`
  - `prophet_lower: int`
  - `prophet_upper: int`
  - `confidence: str`
  - `model_path: str`
- Required vs optional: all fields required.
- Allowed values:
  - `confidence` currently returns `"HIGH"`, `"MEDIUM"`, or `"LOW"`.
  - `model_path` currently returns one of:
    - `"xgboost_residual_interval"`
    - `"fallback_recent_trend"`
    - `"fallback_unsafe_xgboost_output"`
    - `"prophet"`
    - `"fallback_unsafe_prophet_output"`
- Defaults: none.
- Validation constraints: dataclass only; API validation is handled by caller checks.
- Migration notes: `model_path` was added to track which model produced a forecast.
- Backward compatibility notes: internal Python callers constructing `ForecastPrediction` must now provide `model_path`.

### `ForecastResult`

- Exact name: `ForecastResult`
- Fields:
  - `din: str`
  - `location_id: str`
  - `horizon_days: int`
  - `predicted_quantity: int`
  - `prophet_lower: int`
  - `prophet_upper: int`
  - `confidence: str`
  - `model_path: str`
  - `days_of_supply: float`
  - `avg_daily_demand: float`
  - `reorder_status: str`
  - `reorder_point: float`
  - `generated_at: str`
  - `data_points_used: int`
- Required vs optional: all fields required.
- Allowed values:
  - `reorder_status` is `"GREEN"`, `"AMBER"`, or `"RED"`.
  - `confidence` is `"HIGH"`, `"MEDIUM"`, or `"LOW"`.
- Defaults: none.
- Validation constraints:
  - `predicted_quantity >= 0`
  - `prophet_lower >= 0`
  - `prophet_upper >= 0`
  - `prophet_lower <= prophet_upper`
  - `days_of_supply >= 0`
  - `data_points_used >= 14`
- Migration notes: Spring Boot should add a forecast persistence column such as `model_path text not null default 'unknown'` or equivalent if historical forecast display needs this value.
- Backward compatibility notes: `POST /forecast/drug` response now includes `model_path`.

### `BacktestUploadRequest`

- Exact name: `BacktestUploadRequest`
- Fields:
  - `organization_id: str`
  - `location_id: str`
  - `csv_upload_id: str`
  - `model_version: str`
  - `rows: list[BacktestDemandRow]`
  - `debug_artifacts: bool`
- Required vs optional:
  - Required: `organization_id`, `location_id`, `csv_upload_id`, `rows`
  - Optional/defaulted: `model_version`, `debug_artifacts`
- Allowed values:
  - `rows` must have at least one row.
  - Extra top-level fields are forbidden.
- Defaults:
  - `model_version="xgboost_residual_v1"`
  - `debug_artifacts=false`
- Validation constraints: Pydantic `extra="forbid"`; row validation described below.
- Migration notes: Spring Boot upload-history persistence should store `model_version` from request/response.
- Backward compatibility notes: default model version changed from `prophet_v1` to `xgboost_residual_v1`.

### `BacktestDemandRow`

- Exact name: `BacktestDemandRow`
- Fields:
  - `dispensed_date: str`
  - `din: str`
  - `quantity_dispensed: float`
  - `cost_per_unit: Optional[float]`
- Required vs optional:
  - Required: `dispensed_date`, `din`, `quantity_dispensed`
  - Optional: `cost_per_unit`
- Allowed values:
  - `quantity_dispensed >= 0`
  - `patient_id` is not allowed.
- Defaults:
  - `cost_per_unit=None`
- Validation constraints: Pydantic `extra="forbid"` rejects `patient_id`.
- Migration notes: no migration.
- Backward compatibility notes: callers must not include patient identifiers.

### `BacktestUploadSummary`

- Exact name: `BacktestUploadSummary`
- Fields:
  - `status: Literal["PASS", "LOW_CONFIDENCE", "FAIL", "ERROR"]`
  - `model_version: str`
  - `mae: Optional[float]`
  - `wape: Optional[float]`
  - `interval_coverage: Optional[float]`
  - `anomaly_count: Optional[int]`
  - `beats_last_7_day_avg: Optional[bool]`
  - `beats_last_14_day_avg: Optional[bool]`
  - `baseline_last_7_day_avg_mae: Optional[float]`
  - `baseline_last_14_day_avg_mae: Optional[float]`
  - `rows_evaluated: Optional[int]`
  - `raw_rows_received: Optional[int]`
  - `usable_rows: Optional[int]`
  - `min_required_rows: Optional[int]`
  - `date_range: Optional[dict[str, Optional[str]]]`
  - `ready_for_forecast: bool`
  - `model_path_counts: dict[str, int]`
  - `din_count: Optional[int]`
  - `generated_at: str`
  - `error_message: Optional[str]`
  - `artifact_path: Optional[str]`
- Required vs optional:
  - Required in response: all keys are present.
  - Nullable metrics are `null` on fail/error paths.
- Allowed values:
  - `status`: `"PASS"`, `"LOW_CONFIDENCE"`, `"FAIL"`, `"ERROR"`
  - `model_path_counts` keys currently include `"xgboost_residual_interval"` for the default model path, or fallback model paths when fallbacks are used.
- Defaults:
  - `ready_for_forecast=false` in schema.
  - `model_path_counts={}` in schema and failure/error payloads.
- Validation constraints:
  - `PASS` requires:
    - `anomaly_count == 0`
    - `beats_last_7_day_avg == true`
    - `beats_last_14_day_avg == true`
    - `wape <= 0.20`
    - `interval_coverage >= 0.75`
  - `LOW_CONFIDENCE` when WAPE is at or below `0.35` but `PASS` criteria are not met.
  - `FAIL` otherwise.
- Migration notes: Spring Boot upload history should store `model_version` and `model_path_counts` if the UI needs to show the model used for backtesting.
- Backward compatibility notes: `model_path_counts` is additive; `PASS` semantics are stricter than before.

## 5. Integration Contract

- Upstream dependencies:
  - Spring Boot calls Python forecast service after server-side organization/location ownership validation.
  - Spring Boot must not send `patient_id`.
  - Spring Boot provides aggregated DIN/location demand rows indirectly through Supabase repository-backed forecast calls or directly in upload backtest payloads.
- Downstream dependencies:
  - Python forecast service uses Supabase repository for live `POST /forecast/drug` and `POST /forecast/batch` history fetches.
  - Python forecast service uses no LLM and no Grok API.
- Services called:
  - Supabase is called by `SupabaseDispensingRepository` for live forecast history. Exact query details are outside this contract.
  - XGBoost is an in-process Python dependency, not an external service call.
- Endpoints hit:
  - Spring Boot should call `POST /forecast/drug` for one DIN.
  - Spring Boot should call `POST /forecast/batch` for multiple DINs.
  - Spring Boot should call `POST /backtest/upload` after CSV upload processing if upload-readiness backtest is needed.
- Events consumed: NOT IMPLEMENTED.
- Events published: NOT IMPLEMENTED.
- Files read or written:
  - Backtest debug mode writes artifacts under `artifacts/backtests/debug/{csv_upload_id}` when `debug_artifacts=true`.
  - Normal backtest requests use temporary directories for intermediate step files and clean them up.
- Environment assumptions:
  - Python environment has `xgboost>=2.0,<4.0`.
  - On macOS local development, XGBoost may require `libomp`.
  - Production Linux image must include any shared libraries required by the selected XGBoost wheel.
- Auth assumptions:
  - Python endpoints do not enforce tenant auth.
  - Spring Boot must validate organization/location ownership before calling Python.
- Retry behavior:
  - NOT IMPLEMENTED in Python.
  - Spring Boot should decide whether failed forecast/backtest calls are retryable.
- Timeout behavior:
  - Single-drug forecasts use `FORECAST_TIMEOUT_SECONDS = 30`.
  - Timeout response is HTTP `503` with `{"error":"forecast_timeout","confidence":"LOW"}`.
- Fallback behavior:
  - XGBoost falls back to `fallback_recent_trend` when weekly history is insufficient.
  - XGBoost falls back to `fallback_unsafe_xgboost_output` if model output contains unsafe values.
  - Prophet remains available and has its own fallback paths.
- Idempotency behavior:
  - `POST /forecast/drug` is computationally repeatable for the same underlying history and request, but it is not formally idempotent because `generated_at` changes.
  - `POST /backtest/upload` is computationally repeatable for identical rows and model version, but `generated_at` changes and debug artifacts can be rewritten.

## 6. Usage Instructions for Other Engineers

- For drug panel details, Spring Boot should persist and return the `model_path` from `POST /forecast/drug`.
- Recommended Spring `forecasts` table addition:
  - Add `model_path text not null` with a backfill value such as `"unknown"` for existing rows, or use nullable with UI fallback if migration risk is lower.
  - Store `"xgboost_residual_interval"` for normal XGBoost forecasts.
  - Store fallback paths when Python returns them.
- For upload history, Spring Boot should persist:
  - `model_version`
  - `model_path_counts`
  - `status`
  - `ready_for_forecast`
  - `mae`
  - `wape`
  - `interval_coverage`
  - `beats_last_7_day_avg`
  - `beats_last_14_day_avg`
  - `baseline_last_7_day_avg_mae`
  - `baseline_last_14_day_avg_mae`
  - `rows_evaluated`
  - `din_count`
  - `generated_at`
  - `error_message`
- Suggested upload-history display:
  - Display `model_version` as the backtest version: `xgboost_residual_v1`.
  - Display `model_path_counts` as model execution breakdown, e.g. `xgboost_residual_interval: 72`.
  - Display `ready_for_forecast` as the gating field.
- Loading states:
  - Forecast generation can take up to 30 seconds per DIN before timing out.
  - Batch forecasts stream per-DIN completion events; do not wait for all DINs before updating progress.
- Empty states:
  - Handle `insufficient_data` with minimum row message.
  - Handle `insufficient_backtest_history` in upload history as `FAIL`, not as transport failure.
- Success states:
  - Treat `POST /forecast/drug` HTTP `200` as a publishable forecast.
  - Treat `POST /backtest/upload` `status == "PASS"` and `ready_for_forecast == true` as upload-ready by current Python criteria.
- Failure states:
  - `LOW_CONFIDENCE` means the upload backtest has usable metrics but did not clear the stricter acceptance bar.
  - `FAIL` means not ready for forecast trust.
  - `ERROR` means Python encountered an unhandled backtest error; HTTP status is `500`.
- Finalized:
  - `model_path` in forecast response.
  - `model_version` and `model_path_counts` in backtest response.
  - `X-Forecast-Code-Path: weekly-xgboost-residual-v1`.
- Provisional:
  - Field names `prophet_lower` and `prophet_upper` remain unchanged for backward compatibility even when XGBoost produced the interval.
  - Exact XGBoost hyperparameters may change after more real pharmacy datasets are evaluated.
- Mocked or stubbed:
  - Tests use fake repositories and fake model runners.
  - No persisted trained model registry exists.
- Must not be changed without coordination:
  - Do not remove `patient_id` rejection.
  - Do not loosen `PASS` criteria without business approval.
  - Do not rename `prophet_lower`/`prophet_upper` until Spring and frontend contracts are updated together.

## 7. Security and Authorization Notes

- Python forecast service does not enforce authentication or authorization.
- Spring Boot must validate organization and location ownership server-side before calling Python.
- `patient_id` must never be sent to Python backtest upload; `BacktestDemandRow` rejects it.
- `patient_id` must never be sent to Grok, LLMs, external APIs, logs, prompts, exports, generated documents, or upload backtests.
- `POST /forecast/drug` response explicitly strips any `patient_id` if a lower layer accidentally returns it. The Spring contract test verifies this.
- Forecast/backtest model metadata is not patient data. It is safe to display to authorized users within the tenant.
- Python logs include `din`, `location_id`, record counts, date ranges, and aggregate quantity. They must not include `patient_id`.
- Supabase RLS is not enough by itself; Spring Boot must enforce tenancy before calling Python.

## 8. Environment and Configuration

- `SUPABASE_URL`
  - Purpose: Supabase project URL for repository-backed live forecast history.
  - Required or optional: optional for health/app import; required for live Supabase-backed forecasting.
  - Default behavior if missing: `None`.
  - Dev vs prod notes: local health tests do not require it; production forecast calls need it.
- `SUPABASE_SERVICE_KEY`
  - Purpose: Supabase service key for repository-backed live forecast history.
  - Required or optional: optional for health/app import; required for live Supabase-backed forecasting.
  - Default behavior if missing: `None`.
  - Dev vs prod notes: must be treated as a secret.
- `PORT`
  - Purpose: Uvicorn port in Docker/runtime.
  - Required or optional: optional.
  - Default behavior if missing: `8000`.
  - Dev vs prod notes: Dockerfile uses `${PORT:-8000}`.
- Python dependency `xgboost>=2.0,<4.0`
  - Purpose: in-process XGBoost model training and prediction.
  - Required or optional: required for default forecast and backtest behavior.
  - Default behavior if missing: forecast raises `forecast_dependencies_missing`.
  - Dev vs prod notes: macOS local development may require `brew install libomp`.
- Python dependency `prophet>=1.1,<2.0`
  - Purpose: retained comparison/fallback implementation.
  - Required or optional: declared runtime dependency.
  - Default behavior if missing: Prophet-specific runner raises `forecast_dependencies_missing`.
  - Dev vs prod notes: default path no longer uses Prophet.

## 9. Testing and Verification

- Tests added or updated:
  - `tests/forecast_service/test_drug_forecast.py`
  - `tests/forecast_service/test_spring_forecast_contract.py`
  - `tests/forecast_service/test_backtest_upload.py`
  - `tests/forecasting/test_backtest.py`
  - `tests/forecast_service/test_foundation_structure.py`
- Manual verification:
  - Installed `xgboost` locally.
  - Installed `libomp` locally because macOS XGBoost wheel required `libomp.dylib`.
  - Verified upload-style rolling-origin fixture returns `PASS`.
  - Verified `POST /forecast/drug` Spring contract includes `model_path` and excludes `patient_id`.
- How to run tests:
  ```bash
  python3 -m pytest -q
  ```
- Focused verification run after exposing `model_path`:
  ```bash
  python3 -m pytest tests/forecast_service/test_drug_forecast.py tests/forecast_service/test_spring_forecast_contract.py tests/forecast_service/test_backtest_upload.py -q
  ```
- Latest observed focused result:
  - `21 passed`
  - `14 warnings`
- Latest observed full result before the final `model_path` API exposure:
  - `33 passed`
  - `14 warnings`
- Known warnings:
  - Prophet/matplotlib/pyparsing deprecation warnings appear in Prophet fallback tests.
- Known gaps in test coverage:
  - No Spring Boot migration tests exist in this repo.
  - No frontend display tests exist in this repo.
  - No production Docker build with XGBoost is verified in this repo.
  - No multi-tenant auth tests exist in Python because auth is owned by Spring Boot.

## 10. Known Limitations and TODOs

- Direct 1-period fixture still does not beat both simple baselines; upload-style rolling-origin fixture does.
- The model should not yet be marketed as universally enterprise-grade across all pharmacy datasets without more real-world validation.
- XGBoost trains per forecast request; there is no model artifact cache, model registry, or scheduled retraining.
- Prediction interval fields are still named `prophet_lower` and `prophet_upper` for backward compatibility even when XGBoost produced the interval.
- `model_path_counts` is a map rather than a single field because rolling-origin backtests can use fallback paths for some rows.
- Backtest artifacts under `artifacts/backtests/debug/{csv_upload_id}` are only written when `debug_artifacts=true`; Python does not persist artifacts to external storage.
- Python does not write forecast or backtest results to Supabase; Spring Boot must persist them.
- Docker image may need platform-specific shared libraries for XGBoost depending on deployment base image.
- Additional real pharmacy datasets are needed to tune acceptance bars per DIN and per therapeutic class.

## 11. Source of Truth Snapshot

- Final model version default: `xgboost_residual_v1`
- Final primary model path: `xgboost_residual_interval`
- Final forecast code path header: `X-Forecast-Code-Path: weekly-xgboost-residual-v1`
- Final routes:
  - `POST /forecast/drug`
  - `POST /forecast/batch`
  - `POST /forecast/notification-check`
  - `POST /backtest/upload`
- Final DTO/model names:
  - `DrugForecastRequest`
  - `BatchForecastRequest`
  - `ForecastThreshold`
  - `NotificationCheckRequest`
  - `BacktestUploadRequest`
  - `BacktestDemandRow`
  - `BacktestUploadSummary`
  - `ForecastPrediction`
  - `ForecastResult`
- Final status values:
  - Forecast confidence: `"HIGH" | "MEDIUM" | "LOW"`
  - Reorder status: `"GREEN" | "AMBER" | "RED"`
  - Backtest status: `"PASS" | "LOW_CONFIDENCE" | "FAIL" | "ERROR"`
- Final key files:
  - `apps/forecast_service/app/services/model.py`
  - `apps/forecast_service/app/services/forecasting.py`
  - `apps/forecast_service/app/api/forecasts.py`
  - `apps/forecast_service/app/services/backtesting.py`
  - `apps/forecast_service/app/schemas/backtest.py`
  - `forecasting/model.py`
  - `forecasting/backtest_core.py`
- Breaking or additive changes from previous version:
  - Additive: `POST /forecast/drug` success response includes `model_path`.
  - Additive: `POST /backtest/upload` response includes `model_path_counts`.
  - Behavior change: default model changed from Prophet to XGBoost.
  - Behavior change: `PASS` now requires beating both baselines, not either baseline.
  - Behavior change: default backtest `model_version` changed from `prophet_v1` to `xgboost_residual_v1`.

## 12. Copy-Paste Handoff for the Next Engineer

The Python forecast service now defaults to `xgboost_residual_v1`, with normal forecasts reporting `model_path: "xgboost_residual_interval"`. Spring Boot can safely depend on `model_path` in `POST /forecast/drug` responses, and on `model_version` plus `model_path_counts` in `POST /backtest/upload` responses.

To show model usage in the drug panel, persist `model_path` on forecast records and return it through the backend forecast-details API. To show model usage in upload history, persist `model_version` and `model_path_counts` from the upload backtest summary.

The main traps are that `prophet_lower` and `prophet_upper` are legacy field names now used for XGBoost intervals, Python does not enforce tenant auth, and `patient_id` must never be sent or persisted in model/backtest artifacts. Read sections 3, 4, and 7 first.
