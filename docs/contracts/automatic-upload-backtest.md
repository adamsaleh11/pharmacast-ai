# Implementation Handoff Contract

## 1. Summary

- What was implemented: NOT IMPLEMENTED in Spring Boot yet. This contract defines the backend implementation for automatic summary-only backtesting after each successful CSV upload.
- Why it is being implemented: each pharmacy/location upload must be quality-gated before forecasts are treated as trustworthy. Backtesting verifies the current forecast policy against the uploaded historical data and stores a compact forecast-readiness summary.
- What is in scope:
  - Trigger a backtest automatically after CSV upload rows are validated and persisted.
  - Run the backtest using sanitized drug-level historical demand only.
  - Store a compact JSON summary in `csv_uploads.validation_summary`.
  - Mark forecast readiness as `PASS`, `LOW_CONFIDENCE`, `FAIL`, or `ERROR`.
  - Keep full artifact files optional and disabled by default.
- What is out of scope:
  - Changing model code during backtesting.
  - Training a custom model per pharmacy.
  - Persisting full backtest artifacts by default.
  - Sending `patient_id` to Python, Grok, LLMs, logs, exports, prompts, or generated documents.
  - Frontend UI redesign.
  - Spring Boot database migrations beyond fields/tables explicitly listed in this contract.
- Which repo/service/module owns this implementation:
  - Spring Boot backend owns CSV upload orchestration, organization/location authorization, persistence, async triggering, and saving the summary.
  - Python `forecast_service` owns numeric forecast execution, backtest metrics, baseline comparison, and summary calculation.

## 2. Files Added or Changed

- `docs/contracts/automatic-upload-backtest.md`: created. Source-of-truth implementation contract for automatic backtesting after CSV upload.
- Spring Boot CSV upload controller: TO IMPLEMENT. The exact file path is UNDECIDED because the Spring Boot backend is not present in this repo.
- Spring Boot CSV upload service: TO IMPLEMENT. It must trigger the backtest after successful persistence.
- Spring Boot forecast/backtest client: TO IMPLEMENT. It must call the Python forecast service backtest interface or local runner adapter.
- Spring Boot `csv_uploads` persistence code: TO UPDATE. It must save `validation_summary.backtest`.
- Python `forecast_service` backtest endpoint or internal runner adapter: TO IMPLEMENT if the backend chooses HTTP integration. Exact file paths should follow existing Python conventions:
  - `apps/forecast_service/app/api/`
  - `apps/forecast_service/app/schemas/`
  - `apps/forecast_service/app/services/`
- Existing Python backtest modules available to reuse:
  - `forecasting/backtest_core.py`: existing `BacktestRunner`, `BacktestRunConfig`, `BacktestRunResult`.
  - `forecasting/model.py`: existing backtest forecaster mirroring production forecast policy.
  - `forecasting/metrics.py`: existing baseline and regression metrics.
  - `forecasting/data.py`: existing CSV validation and weekly aggregation helpers.

## 3. Public Interface Contract

### Spring Boot CSV Upload Completion Hook

- Name: `CsvUploadBacktestTrigger`
- Type: backend service workflow hook
- Purpose: run automatic backtesting after a CSV upload has been validated and persisted.
- Owner: Spring Boot backend.
- Inputs:
  - `organizationId: UUID`
  - `locationId: UUID`
  - `csvUploadId: UUID`
  - persisted rows or normalized upload rows containing only allowed forecasting fields
- Outputs:
  - Updates `csv_uploads.validation_summary` with `backtest`.
  - Updates `csv_uploads.status` to `SUCCESS` or `ERROR` according to existing upload status behavior.
- Required fields:
  - `organizationId`
  - `locationId`
  - `csvUploadId`
  - historical demand rows with `dispensed_date`, `din`, `quantity_dispensed`, and optional `cost_per_unit`
- Optional fields:
  - `debug_artifacts`, default `false`
- Validation rules:
  - Backend must validate organization/location ownership before triggering the backtest.
  - Backend must not send `patient_id`.
  - Backend must not trigger trusted forecast readiness if persistence failed.
- Defaults:
  - `model_version = "prophet_v1"`
  - `debug_artifacts = false`
- Status codes or result states:
  - Not an HTTP interface by itself.
  - Final backtest status values: `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Error shapes:
  - Store backtest errors in `csv_uploads.validation_summary.backtest.error_message`.
  - Do not expose stack traces to users.
- Example input:

```json
{
  "organizationId": "11111111-1111-1111-1111-111111111111",
  "locationId": "22222222-2222-2222-2222-222222222222",
  "csvUploadId": "33333333-3333-3333-3333-333333333333"
}
```

- Example output persisted in `csv_uploads.validation_summary`:

```json
{
  "backtest": {
    "status": "PASS",
    "model_version": "prophet_v1",
    "mae": 2.77,
    "wape": 0.018,
    "interval_coverage": 0.916,
    "anomaly_count": 0,
    "beats_last_7_day_avg": true,
    "beats_last_14_day_avg": true,
    "rows_evaluated": 60,
    "din_count": 5,
    "generated_at": "2026-04-21T05:00:00Z"
  }
}
```

### Python Forecast Service Backtest Interface

- Name: `POST /backtest/upload`
- Type: HTTP endpoint to implement in Python `forecast_service`.
- Purpose: run a summary-only backtest over sanitized uploaded historical demand rows and return forecast-readiness metrics.
- Owner: Python `forecast_service`.
- Inputs: JSON body matching `BacktestUploadRequest`.
- Outputs: JSON body matching `BacktestUploadSummary`.
- Required fields:
  - `organization_id: string`
  - `location_id: string`
  - `csv_upload_id: string`
  - `model_version: string`
  - `rows: BacktestDemandRow[]`
- Optional fields:
  - `debug_artifacts: boolean`
- Validation rules:
  - `rows` must not be empty.
  - Each row must include `dispensed_date`, `din`, and `quantity_dispensed`.
  - `quantity_dispensed` must be numeric and `>= 0`.
  - `cost_per_unit` may be omitted or null.
  - `patient_id` is forbidden.
  - Any unexpected patient identifier field must reject the request.
- Defaults:
  - `debug_artifacts = false`
  - `model_version = "prophet_v1"` if backend does not pass a value.
- Status codes or result states:
  - `200 OK` for completed backtest with status `PASS`, `LOW_CONFIDENCE`, or `FAIL`.
  - `422 Unprocessable Entity` for invalid request body or forbidden patient fields.
  - `500 Internal Server Error` only for unexpected service failures.
- Error shapes:

```json
{
  "status": "ERROR",
  "model_version": "prophet_v1",
  "error_message": "insufficient_backtest_history",
  "generated_at": "2026-04-21T05:00:00Z"
}
```

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
  "mae": 2.77,
  "wape": 0.018,
  "interval_coverage": 0.916,
  "anomaly_count": 0,
  "beats_last_7_day_avg": true,
  "beats_last_14_day_avg": true,
  "rows_evaluated": 60,
  "din_count": 5,
  "generated_at": "2026-04-21T05:00:00Z"
}
```

### Optional Debug Artifact Mode

- Name: `debug_artifacts`
- Type: boolean request flag.
- Purpose: allow engineers to write full artifacts for diagnosis without making artifacts part of normal product behavior.
- Owner: Python `forecast_service`.
- Inputs:
  - `debug_artifacts: true`
- Outputs:
  - Optional artifact path in response.
- Required fields:
  - Same request fields as `POST /backtest/upload`.
- Optional fields:
  - `artifact_path` in response.
- Validation rules:
  - Must default to `false`.
  - Must never write `patient_id`.
- Defaults:
  - `false`
- Status codes or result states:
  - Same as `POST /backtest/upload`.
- Error shapes:
  - Same as `POST /backtest/upload`.
- Example input:

```json
{
  "debug_artifacts": true
}
```

- Example output addition:

```json
{
  "artifact_path": "artifacts/backtests/debug/33333333-3333-3333-3333-333333333333"
}
```

## 4. Data Contract

### `BacktestDemandRow`

- Exact name: `BacktestDemandRow`
- Fields:
  - `dispensed_date: string`, required, format `YYYY-MM-DD`.
  - `din: string`, required, Health Canada DIN string. Preserve leading zeros.
  - `quantity_dispensed: number`, required, `>= 0`.
  - `cost_per_unit: number | null`, optional.
- Allowed values:
  - `quantity_dispensed` must be numeric.
  - `cost_per_unit` must be numeric when present.
- Defaults:
  - `cost_per_unit = null` when missing.
- Validation constraints:
  - Reject blank `din`.
  - Reject invalid dates.
  - Reject negative `quantity_dispensed`.
  - Reject any `patient_id` field.
- Migration notes:
  - No migration required for this DTO.
- Backward compatibility notes:
  - Matches existing backtest CSV columns: `dispensed_date`, `din`, `quantity_dispensed`, `cost_per_unit`.

### `BacktestUploadRequest`

- Exact name: `BacktestUploadRequest`
- Fields:
  - `organization_id: string`, required.
  - `location_id: string`, required.
  - `csv_upload_id: string`, required.
  - `model_version: string`, required.
  - `rows: BacktestDemandRow[]`, required.
  - `debug_artifacts: boolean`, optional.
- Allowed values:
  - `model_version = "prophet_v1"` for the current model.
  - `debug_artifacts = true | false`.
- Defaults:
  - `debug_artifacts = false`.
- Validation constraints:
  - `rows.length > 0`.
  - No patient identifiers.
- Migration notes:
  - No migration required for this request shape.
- Backward compatibility notes:
  - New interface; no previous version.

### `BacktestUploadSummary`

- Exact name: `BacktestUploadSummary`
- Fields:
  - `status: string`, required.
  - `model_version: string`, required.
  - `mae: number | null`, optional on `ERROR`.
  - `wape: number | null`, optional on `ERROR`.
  - `interval_coverage: number | null`, optional on `ERROR`.
  - `anomaly_count: integer | null`, optional on `ERROR`.
  - `beats_last_7_day_avg: boolean | null`, optional on `ERROR`.
  - `beats_last_14_day_avg: boolean | null`, optional on `ERROR`.
  - `rows_evaluated: integer | null`, optional on `ERROR`.
  - `din_count: integer | null`, optional on `ERROR`.
  - `generated_at: string`, required, UTC ISO-8601 timestamp.
  - `error_message: string | null`, optional.
  - `artifact_path: string | null`, optional and only populated when `debug_artifacts = true`.
- Allowed values:
  - `status`: `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Defaults:
  - `artifact_path = null`.
  - `error_message = null`.
- Validation constraints:
  - Numeric metrics must be non-negative when present.
  - `interval_coverage` must be between `0.0` and `1.0` when present.
- Migration notes:
  - Store under `csv_uploads.validation_summary.backtest` for v1.
- Backward compatibility notes:
  - `csv_uploads.validation_summary` already exists in the core data model as nullable JSON.

### `csv_uploads.validation_summary.backtest`

- Exact name: `csv_uploads.validation_summary.backtest`
- Fields:
  - Same shape as `BacktestUploadSummary`.
- Field types:
  - JSON object inside existing `validation_summary jsonb`.
- Required vs optional:
  - Required after a successful CSV import and attempted backtest.
  - Optional before backtest starts or for legacy uploads.
- Allowed values:
  - `status`: `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Defaults:
  - `null` for uploads created before this feature.
- Validation constraints:
  - Backend should write the object atomically after receiving the Python summary.
- Migration notes:
  - No new table required for v1 if `csv_uploads.validation_summary` exists.
  - If the current database does not yet include `validation_summary`, add it as `jsonb nullable`.
- Backward compatibility notes:
  - Existing consumers must tolerate `validation_summary` being null or missing `backtest`.

## 5. Integration Contract

- Upstream dependencies:
  - Frontend CSV upload flow.
  - Spring Boot CSV upload controller/service.
  - Supabase/PostgreSQL `csv_uploads`.
  - Supabase/PostgreSQL `dispensing_records`.
- Downstream dependencies:
  - Python `forecast_service`.
  - Existing Python `forecasting` backtest modules.
- Services called:
  - Spring Boot calls Python `POST /backtest/upload` after upload persistence succeeds.
- Endpoints hit:
  - `POST /backtest/upload` on Python `forecast_service`, TO IMPLEMENT.
- Events consumed:
  - NOT IMPLEMENTED. No queue/event bus in v1.
- Events published:
  - NOT IMPLEMENTED. No queue/event bus in v1.
- Files read or written:
  - Normal production path must not depend on artifact files.
  - Optional debug mode may write under `artifacts/backtests/debug/<csv_upload_id>/`.
- Environment assumptions:
  - Spring Boot can reach Python forecast service over HTTP.
  - Python service has required forecasting dependencies installed.
  - All services are hosted in Canada in production.
- Auth assumptions:
  - Spring Boot validates organization/location ownership before calling Python.
  - Python endpoint is intended for trusted backend-to-service traffic only.
  - Python does not perform tenant authorization in v1.
- Retry behavior:
  - Spring Boot may retry the Python call once for transient network failure.
  - Spring Boot must not duplicate dispensing records when retrying the backtest.
  - Retrying a backtest for the same `csv_upload_id` should replace `validation_summary.backtest`.
- Timeout behavior:
  - Spring Boot HTTP client timeout should be finite; recommended initial timeout is `60` seconds.
  - If timeout occurs, store `status = "ERROR"` and `error_message = "backtest_timeout"`.
- Fallback behavior:
  - If backtest fails, CSV upload can still be marked imported according to existing product rules, but forecast readiness must be `ERROR` or `FAIL`.
  - Forecast generation should not be marked trusted when latest backtest status is `ERROR` or `FAIL`.
- Idempotency behavior:
  - The backtest is idempotent for the same `csv_upload_id`, `model_version`, and rows.
  - Reuploading historical data creates a new `csv_upload_id` or replaces the latest summary for that upload.
  - The latest upload summary should be the source of truth for current location forecast readiness.

## 6. Usage Instructions for Other Engineers

- Backend engineers can rely on:
  - `csv_uploads.validation_summary` as the v1 persistence location for backtest summary.
  - Python backtest metrics names from this contract.
  - Status values: `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Backend engineers should call:
  - `POST /backtest/upload` after CSV rows are validated and persisted.
- Backend engineers must provide:
  - `organization_id`
  - `location_id`
  - `csv_upload_id`
  - `model_version`
  - sanitized demand rows with `dispensed_date`, `din`, `quantity_dispensed`, optional `cost_per_unit`
- Backend engineers will receive:
  - A compact `BacktestUploadSummary`.
- Loading states to handle:
  - Upload persisted but backtest not started.
  - Backtest in progress.
  - Backtest completed with `PASS`.
  - Backtest completed with `LOW_CONFIDENCE`.
  - Backtest completed with `FAIL`.
  - Backtest errored with `ERROR`.
- Empty states to handle:
  - `validation_summary = null`.
  - `validation_summary.backtest = null`.
  - `rows_evaluated = 0`.
- Success states to handle:
  - `status = "PASS"` means forecasts can be shown as forecast-ready for the latest upload.
  - `status = "LOW_CONFIDENCE"` means forecasts may be shown with caution or fallback labeling.
- Failure states to handle:
  - `status = "FAIL"` means data did not pass the quality gate.
  - `status = "ERROR"` means the backtest did not complete.
- What is finalized:
  - Summary fields.
  - Status values.
  - No patient identifiers in Python request.
  - Summary-only production behavior.
- What is still provisional:
  - Exact Spring Boot class names and file paths.
  - Exact Python endpoint file locations.
  - Whether the backtest runs synchronously in the upload request or asynchronously after upload.
- What is mocked or stubbed:
  - NOT IMPLEMENTED.
- What must not be changed without coordination:
  - Do not make backtests mutate model code or model settings per pharmacy.
  - Do not store full artifacts as required product state.
  - Do not send `patient_id` outside Spring Boot persistence boundaries.

## 7. Security and Authorization Notes

- Auth requirements:
  - The frontend upload request must be authenticated through existing Spring Security.
  - Spring Boot must resolve the authenticated principal and organization.
- Permission rules:
  - User must belong to the organization that owns the `location_id`.
  - Spring Boot must validate location ownership before writing records or triggering backtest.
- Tenancy rules:
  - Never trust Python or Supabase RLS alone for tenant authorization.
  - Spring Boot remains the tenant enforcement boundary.
- Role checks:
  - Current product model lists `users.role = 'owner'`. If additional roles are added later, CSV upload/backtest triggering must be explicitly permissioned.
- Data isolation:
  - Backtest request rows must be for exactly one `organization_id` and one `location_id`.
- Sensitive fields:
  - `patient_id` is forbidden in the Python request.
  - Supabase service keys must never be logged.
- Sanitization:
  - Backend must strip or omit `patient_id` before Python call.
  - Backend must preserve DIN leading zeros.
- Forbidden fields:
  - `patient_id`
  - user email
  - patient names
  - patient metadata
  - prompt/chat/LLM content
- Logging restrictions:
  - Do not log raw CSV rows.
  - Do not log `patient_id`.
  - Do not log Supabase service keys.
  - Safe to log aggregate counts, `csv_upload_id`, `organization_id`, `location_id`, status, duration, and metric summary.
- Compliance concerns:
  - All data must stay in Canada for PHIPA/PIPEDA.
  - Python service and Spring Boot deployment targets must remain in Canadian regions.
  - No LLM/Grok calls are involved in backtesting.

## 8. Environment and Configuration

- `FORECAST_SERVICE_BASE_URL`
  - Purpose: Spring Boot base URL for Python `forecast_service`.
  - Required or optional: required for Spring Boot HTTP integration.
  - Default behavior if missing: backtest trigger must fail with `status = "ERROR"` and `error_message = "forecast_service_not_configured"`.
  - Dev vs prod notes: local dev may use `http://127.0.0.1:8000`; production must use the Fly.io Toronto forecast service URL.
- `BACKTEST_ON_UPLOAD_ENABLED`
  - Purpose: feature flag for automatic backtesting after upload.
  - Required or optional: optional.
  - Default behavior if missing: recommended default `true` in local/prod after implementation is stable.
  - Dev vs prod notes: can be set `false` while debugging CSV upload independently.
- `BACKTEST_DEBUG_ARTIFACTS_ENABLED`
  - Purpose: allow optional debug artifact generation.
  - Required or optional: optional.
  - Default behavior if missing: `false`.
  - Dev vs prod notes: `false` in production unless explicitly debugging.
- `BACKTEST_HTTP_TIMEOUT_SECONDS`
  - Purpose: Spring Boot timeout for Python backtest call.
  - Required or optional: optional.
  - Default behavior if missing: recommended `60`.
  - Dev vs prod notes: increase only if large uploads require it.
- Existing Python config:
  - `SUPABASE_URL`: not required for row-passing `POST /backtest/upload`; required for existing Supabase-backed forecast endpoints.
  - `SUPABASE_SERVICE_KEY`: not required for row-passing `POST /backtest/upload`; required for existing Supabase-backed forecast endpoints.
  - `PORT`: existing Python service port, defaults to `8000`.

## 9. Testing and Verification

- Tests to add in Spring Boot:
  - CSV upload success triggers one backtest call.
  - Backtest request excludes `patient_id`.
  - Backtest summary is saved under `csv_uploads.validation_summary.backtest`.
  - Python timeout stores `status = "ERROR"` and does not mark forecast-ready.
  - Organization/location ownership is validated before triggering backtest.
  - Reupload replaces latest backtest summary for the new upload.
- Tests to add in Python:
  - `POST /backtest/upload` rejects rows containing `patient_id`.
  - `POST /backtest/upload` returns `PASS` for known good fixture.
  - `POST /backtest/upload` returns `FAIL` or `LOW_CONFIDENCE` when metrics fail quality gate.
  - `debug_artifacts = false` writes no artifact files.
  - `debug_artifacts = true` writes artifacts only under the debug path.
- Existing verification available now:
  - `python3 -m pytest`
  - Existing result after current forecast fix: `28 passed`.
  - Existing rolling-origin backtest result: MAE about `2.7658`, WAPE about `0.0183`, interval coverage about `0.9167`, anomaly count `0`, beats both baselines overall.
- How to locally validate the feature after implementation:
  - Start Python forecast service.
  - Upload `pharmaforecast_backtesting/pharmaforecast_test_dispensing_v2 copy.csv` through Spring Boot upload flow.
  - Confirm `csv_uploads.validation_summary.backtest.status` is populated.
  - Confirm no `patient_id` was sent to Python.
  - Confirm UI/backend reports forecast readiness from the stored summary.
- Known gaps in test coverage:
  - Real Spring Boot code is not present in this repo, so this contract does not include exact Java test file paths.
  - No production object-storage artifact behavior is required for v1.

## 10. Known Limitations and TODOs

- Spring Boot implementation is not present in this repo.
- Python `POST /backtest/upload` is not implemented yet.
- Exact Java package/class names are UNDECIDED.
- Exact async execution mechanism is UNDECIDED; recommended v1 is Spring `@Async` after upload persistence.
- Summary-only mode is the required production default; debug artifact mode is optional.
- Large CSV uploads may need batching or an async job status in the UI.
- Current quality gate thresholds are initial recommendations:
  - `anomaly_count = 0`
  - no negative forecasts
  - `wape <= 0.20`
  - `beats_last_7_day_avg = true OR beats_last_14_day_avg = true`
  - enough rows evaluated
- Enterprise thresholds should be tightened later:
  - `wape <= 0.10` to `0.15` for high-volume DINs
  - `interval_coverage >= 0.75`
  - beats both baselines overall
- Backtesting should not block CSV persistence forever. If backtest fails, preserve upload error/readiness state separately from raw upload persistence.

## 11. Source of Truth Snapshot

- Final interface names:
  - `CsvUploadBacktestTrigger`
  - `POST /backtest/upload`
  - `BacktestUploadRequest`
  - `BacktestDemandRow`
  - `BacktestUploadSummary`
- Final route names:
  - `POST /backtest/upload`, TO IMPLEMENT in Python.
- Final DTO/model names:
  - `BacktestDemandRow`
  - `BacktestUploadRequest`
  - `BacktestUploadSummary`
- Final enum/status values:
  - `PASS`
  - `LOW_CONFIDENCE`
  - `FAIL`
  - `ERROR`
- Final event names:
  - NOT IMPLEMENTED.
- Final file paths of key implementation pieces:
  - `docs/contracts/automatic-upload-backtest.md`
  - `forecasting/backtest_core.py`
  - `forecasting/model.py`
  - `forecasting/metrics.py`
  - `forecasting/data.py`
- Breaking changes from previous version:
  - None. This is a new upload quality-gate workflow.

## 12. Copy-Paste Handoff for the Next Engineer

Automatic backtesting after CSV upload is not implemented in Spring Boot yet. The Python repo already has reusable backtest machinery in `forecasting/backtest_core.py`, model parity in `forecasting/model.py`, and metrics in `forecasting/metrics.py`.

It is safe to depend on the summary shape in this contract, the status values `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`, and storing the v1 summary under `csv_uploads.validation_summary.backtest`.

Build Spring Boot so upload success triggers a sanitized, patient-free backtest request to Python `POST /backtest/upload`, then persist only the returned summary. Do not make backtests mutate model code. Do not require artifact files for product behavior. Read sections 3, 4, 5, and 7 first.
