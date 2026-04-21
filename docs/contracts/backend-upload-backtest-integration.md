# Implementation Handoff Contract

## 1. Summary

- What was implemented: Python `forecast_service` now exposes `POST /backtest/upload` for summary-only uploaded CSV backtesting.
- Why it was implemented: Spring Boot needs a stable service interface to quality-gate each pharmacy/location CSV upload before forecasts are treated as trusted.
- What is in scope: backend integration with `POST /backtest/upload`, patient-free row payload construction, async trigger after CSV persistence, and saving the returned summary under `csv_uploads.validation_summary.backtest`.
- What is out of scope: Spring Boot implementation in this repo, frontend display work, model training, per-pharmacy model mutation, Grok/LLM logic, and required persistent backtest artifacts.
- Which repo/service/module owns this implementation: Python owns `apps.forecast_service`; Spring Boot owns upload authorization, persistence, trigger orchestration, and database summary storage.

## 2. Files Added or Changed

- `apps/forecast_service/app/api/backtests.py`: created. Defines `POST /backtest/upload`.
- `apps/forecast_service/app/api/__init__.py`: updated. Includes the backtest router.
- `apps/forecast_service/app/schemas/backtest.py`: created. Defines `BacktestDemandRow`, `BacktestUploadRequest`, and `BacktestUploadSummary`.
- `apps/forecast_service/app/services/backtesting.py`: created. Runs rolling-origin backtests from uploaded rows and returns compact readiness summaries.
- `tests/forecast_service/test_backtest_upload.py`: created. Verifies PASS summary, patient identifier rejection, and insufficient-history FAIL summary through FastAPI.
- `docs/contracts/backend-upload-backtest-integration.md`: created. Backend handoff contract.

## 3. Public Interface Contract

### `POST /backtest/upload`

- Name: `POST /backtest/upload`
- Type: HTTP endpoint.
- Purpose: receive sanitized uploaded historical demand rows and return a summary-only backtest readiness result.
- Owner: Python `forecast_service`, route function `apps.forecast_service.app.api.backtests.backtest_upload`.
- Inputs: JSON body matching `BacktestUploadRequest`.
- Outputs: JSON body matching the fields in `BacktestUploadSummary`.
- Required fields: `organization_id`, `location_id`, `csv_upload_id`, `rows`.
- Optional fields: `model_version`, `debug_artifacts`.
- Validation rules:
  - `rows` must contain at least one item.
  - Each row requires `dispensed_date`, `din`, and `quantity_dispensed`.
  - `quantity_dispensed` must be `>= 0`.
  - `cost_per_unit` is optional.
  - Extra fields are forbidden on request and row objects. This rejects `patient_id`.
- Defaults:
  - `model_version = "prophet_v1"`.
  - `debug_artifacts = false`.
- Status codes or result states:
  - HTTP `200` when summary `status` is `PASS`, `LOW_CONFIDENCE`, or `FAIL`.
  - HTTP `422` for request validation failures, including forbidden `patient_id`.
  - HTTP `500` when summary `status` is `ERROR`.
- Error shapes:
  - Validation errors use FastAPI/Pydantic `422` response shape.
  - Runtime errors return the normal summary shape with `status = "ERROR"` and `error_message`.
- Example input:

```json
{
  "organization_id": "11111111-1111-1111-1111-111111111111",
  "location_id": "22222222-2222-2222-2222-222222222222",
  "csv_upload_id": "33333333-3333-3333-3333-333333333333",
  "model_version": "prophet_v1",
  "debug_artifacts": false,
  "rows": [
    {
      "dispensed_date": "2025-12-01",
      "din": "02431327",
      "quantity_dispensed": 54,
      "cost_per_unit": 0.55
    }
  ]
}
```

- Example output:

```json
{
  "status": "PASS",
  "model_version": "prophet_v1",
  "mae": 2.765833333333333,
  "wape": 0.01832891539650983,
  "interval_coverage": 0.9166666666666666,
  "anomaly_count": 0,
  "beats_last_7_day_avg": true,
  "beats_last_14_day_avg": true,
  "baseline_last_7_day_avg_mae": 5.116666666666666,
  "baseline_last_14_day_avg_mae": 4.775,
  "rows_evaluated": 60,
  "raw_rows_received": 100,
  "usable_rows": 100,
  "min_required_rows": 8,
  "date_range": {
    "start": "2025-12-01",
    "end": "2026-04-13"
  },
  "ready_for_forecast": true,
  "model_path_counts": {
    "fallback_recent_trend": 60
  },
  "din_count": 5,
  "generated_at": "2026-04-21T05:00:00+00:00",
  "error_message": null,
  "artifact_path": null
}
```

### `run_uploaded_backtest`

- Name: `run_uploaded_backtest`.
- Type: exported Python function.
- Purpose: service-level entry point behind `POST /backtest/upload`.
- Owner: `apps.forecast_service.app.services.backtesting`.
- Inputs: `BacktestUploadRequest`.
- Outputs: dictionary with `BacktestUploadSummary` fields.
- Required fields: same as `BacktestUploadRequest`.
- Optional fields: same as `BacktestUploadRequest`.
- Validation rules: validates row frame using existing `forecasting.data.validate_input_frame`.
- Defaults: same as `BacktestUploadRequest`.
- Status codes or result states: not an HTTP interface directly.
- Error shapes: returns `ERROR` summary for unexpected exceptions; returns `FAIL` summary for `insufficient_backtest_history`.
- Example input: `run_uploaded_backtest(request)`.
- Example output: same shape as `POST /backtest/upload`.

## 4. Data Contract

### `BacktestDemandRow`

- Exact name: `BacktestDemandRow`.
- Fields:
  - `dispensed_date: str`, required.
  - `din: str`, required.
  - `quantity_dispensed: float`, required, `>= 0`.
  - `cost_per_unit: float | null`, optional, default `null`.
- Allowed values: valid ISO-style date strings accepted by existing CSV validation, nonblank DIN strings, non-negative numeric quantities.
- Defaults: `cost_per_unit = null`.
- Validation constraints: `ConfigDict(extra="forbid")`; `patient_id` is rejected as an extra field.
- Migration notes: no database migration.
- Backward compatibility notes: matches existing CSV columns used by `forecasting.data`.

### `BacktestUploadRequest`

- Exact name: `BacktestUploadRequest`.
- Fields:
  - `organization_id: str`, required.
  - `location_id: str`, required.
  - `csv_upload_id: str`, required.
  - `model_version: str`, optional, default `"prophet_v1"`.
  - `rows: list[BacktestDemandRow]`, required, minimum length `1`.
  - `debug_artifacts: bool`, optional, default `false`.
- Allowed values: `debug_artifacts` is boolean; current supported `model_version` value is `"prophet_v1"`.
- Defaults: `model_version = "prophet_v1"`, `debug_artifacts = false`.
- Validation constraints: `ConfigDict(extra="forbid")`.
- Migration notes: no database migration.
- Backward compatibility notes: new Python API request shape.

### `BacktestUploadSummary`

- Exact name: `BacktestUploadSummary`.
- Fields:
  - `status: "PASS" | "LOW_CONFIDENCE" | "FAIL" | "ERROR"`, required.
  - `model_version: str`, required.
  - `mae: float | null`.
  - `wape: float | null`.
  - `interval_coverage: float | null`.
  - `anomaly_count: int | null`.
  - `beats_last_7_day_avg: bool | null`.
  - `beats_last_14_day_avg: bool | null`.
  - `baseline_last_7_day_avg_mae: float | null`.
  - `baseline_last_14_day_avg_mae: float | null`.
  - `rows_evaluated: int | null`.
  - `raw_rows_received: int | null`.
  - `usable_rows: int | null`.
  - `min_required_rows: int | null`.
  - `date_range: object | null` with `start: string | null` and `end: string | null`.
  - `ready_for_forecast: boolean`.
  - `model_path_counts: object`, mapping model path string to evaluated row count.
  - `din_count: int | null`.
  - `generated_at: str`, required, UTC ISO-8601 string with `+00:00`.
  - `error_message: str | null`.
  - `artifact_path: str | null`.
- Allowed values: `status` must be one of `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Defaults: nullable fields are `null` for errors or insufficient-history failure where metrics do not exist.
- Validation constraints: produced by service code; no response model enforcement is currently attached to the route.
- Migration notes: Spring Boot should persist this object under `csv_uploads.validation_summary.backtest`.
- Backward compatibility notes: existing uploads may have `validation_summary = null` or no `backtest` key.

## 5. Integration Contract

- Upstream dependencies: Spring Boot CSV upload service must call this after CSV rows are validated and persisted.
- Downstream dependencies: Python uses existing `forecasting.backtest_core.BacktestRunner`, `forecasting.data`, and `forecasting.metrics`.
- Services called: Spring Boot calls Python forecast service.
- Endpoints hit: `POST /backtest/upload`.
- Events consumed: NOT IMPLEMENTED.
- Events published: NOT IMPLEMENTED.
- Files read or written:
  - With `debug_artifacts = false`, Python writes only temporary files under a `TemporaryDirectory`; they are cleaned up before response.
  - With `debug_artifacts = true`, Python writes under `artifacts/backtests/debug/<csv_upload_id>/` and returns that path.
- Environment assumptions:
  - Spring Boot has a configured Python forecast service base URL.
  - Python forecast dependencies are installed.
  - For row-passing backtests, Python does not need Supabase credentials.
- Auth assumptions:
  - Spring Boot authenticates the user and authorizes organization/location ownership before calling Python.
  - Python endpoint is trusted backend-to-service traffic and does not enforce tenant ownership.
- Retry behavior:
  - Backend may retry transient Python failures.
  - Retrying the same upload should overwrite `csv_uploads.validation_summary.backtest`, not duplicate records.
- Timeout behavior:
  - Recommended backend client timeout: `60` seconds.
  - Timeout should be stored as `status = "ERROR"` with `error_message = "backtest_timeout"` by Spring Boot.
- Fallback behavior:
  - `insufficient_backtest_history` returns HTTP `200`, `status = "FAIL"`, `rows_evaluated = 0`, `ready_for_forecast = false`, and `error_message = "insufficient_backtest_history"`.
  - Unexpected Python exceptions return HTTP `500`, `status = "ERROR"`.
- Idempotency behavior:
  - Same request rows and `csv_upload_id` produce equivalent metrics except `generated_at`.
  - Backend should treat the latest upload/backtest summary as current forecast readiness.

## 6. Usage Instructions for Other Engineers

- Backend can rely on `POST /backtest/upload` existing and being covered by FastAPI tests.
- Backend should call this endpoint after `dispensing_records` persistence succeeds.
- Backend must provide patient-free rows with exact fields `dispensed_date`, `din`, `quantity_dispensed`, optional `cost_per_unit`.
- Backend receives a summary object and should save it unchanged under `csv_uploads.validation_summary.backtest`.
- Backend should treat `raw_rows_received`, `usable_rows`, `rows_evaluated`, `min_required_rows`, `date_range`, and `ready_for_forecast` as the canonical explanation fields for readiness.
- Backend should persist `model_path_counts` unchanged so frontend can tell whether the backtest used Prophet or fallback.
- Model path values currently produced by Python:
  - `prophet`
  - `fallback_recent_trend`
  - `fallback_unsafe_prophet_output`
- Loading states to handle: upload stored but backtest not started; backtest running; summary stored.
- Empty states to handle: `validation_summary = null`; `validation_summary.backtest = null`.
- Success states to handle: `PASS`, `LOW_CONFIDENCE`.
- Failure states to handle: `FAIL`, `ERROR`, HTTP `422`, HTTP `500`, timeout.
- Finalized: route path, request field names, response field names, status values, patient-field rejection.
- Provisional: exact Spring Boot class names, async orchestration mechanism, frontend display copy.
- Mocked or stubbed: NOT IMPLEMENTED in Spring Boot.
- Must not be changed without coordination: status enum values, response field names, `patient_id` rejection, summary storage key.

## 7. Security and Authorization Notes

- Auth requirements: Spring Boot must authenticate the upload request before calling Python.
- Permission rules: Spring Boot must validate the user owns or can administer the `organization_id` and `location_id`.
- Tenancy rules: one request must contain rows for one organization and one location.
- Role checks: current product model uses owner role; if more roles are added, upload/backtest permission must be explicit.
- Data isolation: Python does not query tenant data for this endpoint; backend sends sanitized rows.
- Sensitive fields: `patient_id` is forbidden and rejected by schema.
- Sanitization: preserve DIN leading zeros; remove patient-level fields before request construction.
- Forbidden fields: `patient_id`, patient names, patient metadata, user email, prompt/chat/LLM content.
- Logging restrictions: do not log raw rows, patient identifiers, service keys, auth tokens, or uploaded file contents.
- Compliance concerns: no LLM/Grok calls are involved; all production services must remain in Canadian regions.

## 8. Environment and Configuration

- `FORECAST_SERVICE_BASE_URL`
  - Purpose: Spring Boot base URL for Python forecast service.
  - Required or optional: required in backend.
  - Default behavior if missing: backend should record `ERROR` with `forecast_service_not_configured`.
  - Dev vs prod notes: local can use `http://127.0.0.1:8000`; prod should use the Canadian-hosted forecast service URL.
- `BACKTEST_ON_UPLOAD_ENABLED`
  - Purpose: backend feature flag for automatic trigger.
  - Required or optional: optional.
  - Default behavior if missing: recommended `true` after integration.
  - Dev vs prod notes: can be `false` during upload-only debugging.
- `BACKTEST_HTTP_TIMEOUT_SECONDS`
  - Purpose: backend HTTP timeout to Python.
  - Required or optional: optional.
  - Default behavior if missing: recommended `60`.
  - Dev vs prod notes: increase only for large-upload profiling.
- Python `SUPABASE_URL`
  - Purpose: existing forecast endpoints.
  - Required or optional: not required by row-passing `POST /backtest/upload`.
  - Default behavior if missing: this endpoint can still work.
  - Dev vs prod notes: still required for existing Supabase-backed forecast calls.
- Python `SUPABASE_SERVICE_KEY`
  - Purpose: existing forecast endpoints.
  - Required or optional: not required by row-passing `POST /backtest/upload`.
  - Default behavior if missing: this endpoint can still work.
  - Dev vs prod notes: still required for existing Supabase-backed forecast calls.

## 9. Testing and Verification

- Tests added:
  - `tests/forecast_service/test_backtest_upload.py::test_backtest_upload_returns_pass_summary_for_uploaded_fixture`.
  - `tests/forecast_service/test_backtest_upload.py::test_backtest_upload_rejects_patient_identifiers`.
  - `tests/forecast_service/test_backtest_upload.py::test_backtest_upload_returns_fail_summary_for_insufficient_history`.
- What was manually verified:
  - Full test suite passes with `31 passed`.
- How to run tests:

```bash
python3 -m pytest
```

- How to locally validate:
  - Start forecast service with `uvicorn apps.forecast_service.app.main:app --reload --port 8000`.
  - POST fixture rows from `pharmaforecast_backtesting/pharmaforecast_test_dispensing_v2 copy.csv` to `/backtest/upload`.
  - Confirm response `status = "PASS"` and `artifact_path = null`.
- Known gaps:
  - Spring Boot integration tests are not present in this repo.
  - No auth is enforced by Python for this internal endpoint.
  - Route does not currently use `response_model=BacktestUploadSummary`.

## 10. Known Limitations and TODOs

- Spring Boot upload trigger remains to be built.
- Frontend readiness display remains to be built.
- Python uses temporary CSV files internally to reuse `BacktestRunner`; with `debug_artifacts = false`, these are cleaned up.
- `debug_artifacts = true` writes local artifacts and should stay disabled in production unless explicitly debugging.
- Quality thresholds are fixed constants in `apps/forecast_service/app/services/backtesting.py`:
  - `MIN_TRAINING_PERIODS = 8`
  - `MAX_ROLLING_ORIGIN_STEPS = 12`
  - `PASS_WAPE_THRESHOLD = 0.20`
  - `LOW_CONFIDENCE_WAPE_THRESHOLD = 0.35`
  - `MIN_INTERVAL_COVERAGE = 0.75`
- Future work may move these thresholds to config after product validation.

## 11. Source of Truth Snapshot

- Final route: `POST /backtest/upload`.
- Final request DTO: `BacktestUploadRequest`.
- Final row DTO: `BacktestDemandRow`.
- Final summary DTO: `BacktestUploadSummary`.
- Final status values: `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Final model path values: `prophet`, `fallback_recent_trend`, `fallback_unsafe_prophet_output`.
- Key Python files:
  - `apps/forecast_service/app/api/backtests.py`
  - `apps/forecast_service/app/schemas/backtest.py`
  - `apps/forecast_service/app/services/backtesting.py`
  - `tests/forecast_service/test_backtest_upload.py`
- Breaking changes: none; this is a new endpoint.

## 12. Copy-Paste Handoff for the Next Engineer

Python now implements `POST /backtest/upload` and returns a compact backtest summary for sanitized uploaded rows. It rejects `patient_id`, returns `PASS` for the known fixture, and returns a normal `FAIL` summary for insufficient history.

It is safe to depend on the route path, DTO field names, status values, and summary storage recommendation `csv_uploads.validation_summary.backtest`. Backend still needs to implement the upload-success trigger, service client, timeout handling, and persistence.

Read sections 3, 4, 5, and 7 first. The main trap is accidentally sending `patient_id` or treating artifact files as product state; do neither.
