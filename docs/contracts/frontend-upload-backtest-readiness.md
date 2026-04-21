# Implementation Handoff Contract

## 1. Summary

- What was implemented: Python `forecast_service` now returns upload backtest readiness summaries through `POST /backtest/upload`; frontend work is NOT IMPLEMENTED in this repo.
- Why it was implemented: users need to know whether an uploaded pharmacy/location CSV is forecast-ready before trusting generated forecasts.
- What is in scope: frontend display contract for upload/backtest readiness once Spring Boot exposes `csv_uploads.validation_summary.backtest`.
- What is out of scope: implementing frontend components in this repo, calling Python directly from the browser, changing forecast model code, and rendering detailed artifact CSV files.
- Which repo/service/module owns this implementation: frontend owns display and user states; Spring Boot owns frontend-facing API; Python owns summary generation.

## 2. Files Added or Changed

- `apps/forecast_service/app/api/backtests.py`: created. Defines Python `POST /backtest/upload`, which frontend must not call directly.
- `apps/forecast_service/app/schemas/backtest.py`: created. Defines the summary fields frontend will eventually receive through Spring Boot.
- `apps/forecast_service/app/services/backtesting.py`: created. Produces `PASS`, `LOW_CONFIDENCE`, `FAIL`, or `ERROR` readiness summaries.
- `tests/forecast_service/test_backtest_upload.py`: created. Verifies summary behavior.
- `docs/contracts/frontend-upload-backtest-readiness.md`: created. Frontend handoff contract.

## 3. Public Interface Contract

### Frontend Backtest Readiness Object

- Name: `backtest`.
- Type: JSON object nested under the upload/readiness data returned by Spring Boot.
- Purpose: tell the UI whether the latest upload is forecast-ready.
- Owner: Spring Boot exposes this to frontend; Python generates the underlying values.
- Inputs: frontend receives this from Spring Boot. The frontend must not call Python `POST /backtest/upload` directly.
- Outputs: UI states, labels, warnings, and forecast readiness gating.
- Required fields when present:
  - `status`
  - `model_version`
  - `generated_at`
- Optional fields:
  - `mae`
  - `wape`
  - `interval_coverage`
  - `anomaly_count`
  - `beats_last_7_day_avg`
  - `beats_last_14_day_avg`
  - `baseline_last_7_day_avg_mae`
  - `baseline_last_14_day_avg_mae`
  - `rows_evaluated`
  - `raw_rows_received`
  - `usable_rows`
  - `min_required_rows`
  - `date_range`
  - `ready_for_forecast`
  - `model_path_counts`
  - `din_count`
  - `error_message`
  - `artifact_path`
- Validation rules:
  - Treat missing `backtest` as `NOT_RUN`.
  - Treat unknown `status` as an error/unsupported state.
  - Do not render `artifact_path` as a user-facing file link in v1.
- Defaults:
  - No default object; `backtest` can be null/missing for legacy uploads or in-progress uploads.
- Status codes or result states:
  - Frontend states: `NOT_RUN`, `RUNNING`, `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
  - Python summary statuses: `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Error shapes:
  - For `ERROR`, show `error_message` if Spring Boot chooses to expose it. Do not show stack traces.
- Example input from Spring Boot:

```json
{
  "upload_id": "33333333-3333-3333-3333-333333333333",
  "status": "SUCCESS",
  "validation_summary": {
    "backtest": {
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
  }
}
```

- Example output behavior:

```text
Show forecast readiness as ready/trusted.
Allow normal Generate Forecast behavior.
Display compact metrics: WAPE 1.8%, interval coverage 91.7%, 5 DINs evaluated.
```

### Python `POST /backtest/upload`

- Name: `POST /backtest/upload`.
- Type: internal service endpoint.
- Purpose: backend-only endpoint that generates the readiness object.
- Owner: Python `forecast_service`.
- Inputs: `BacktestUploadRequest`.
- Outputs: `BacktestUploadSummary`.
- Required fields: `organization_id`, `location_id`, `csv_upload_id`, `rows`.
- Optional fields: `model_version`, `debug_artifacts`.
- Validation rules: extra fields are forbidden; `patient_id` is rejected.
- Defaults: `model_version = "prophet_v1"`, `debug_artifacts = false`.
- Status codes or result states: browser must not call this endpoint directly.
- Error shapes: frontend receives backend-translated upload/readiness state, not raw Python errors.
- Example input: NOT APPLICABLE to frontend direct usage.
- Example output: same summary object shown above after Spring Boot persists/exposes it.

## 4. Data Contract

### `BacktestReadiness`

- Exact name: `BacktestReadiness` recommended frontend type name.
- Fields:
  - `status: "PASS" | "LOW_CONFIDENCE" | "FAIL" | "ERROR"`.
  - `model_version: string`.
  - `mae: number | null`.
  - `wape: number | null`.
  - `interval_coverage: number | null`.
  - `anomaly_count: number | null`.
  - `beats_last_7_day_avg: boolean | null`.
  - `beats_last_14_day_avg: boolean | null`.
  - `baseline_last_7_day_avg_mae: number | null`.
  - `baseline_last_14_day_avg_mae: number | null`.
  - `rows_evaluated: number | null`.
  - `raw_rows_received: number | null`.
  - `usable_rows: number | null`.
  - `min_required_rows: number | null`.
  - `date_range: { start: string | null; end: string | null } | null`.
  - `ready_for_forecast: boolean`.
  - `model_path_counts: Record<string, number>`.
  - `din_count: number | null`.
  - `generated_at: string`.
  - `error_message: string | null`.
  - `artifact_path: string | null`.
- Required vs optional:
  - If `backtest` exists, `status`, `model_version`, and `generated_at` are required.
  - Metrics can be null for `FAIL` and `ERROR`.
- Allowed values:
  - `status`: `PASS`, `LOW_CONFIDENCE`, `FAIL`, `ERROR`.
- Defaults:
  - Missing object means no completed backtest summary is available.
- Validation constraints:
  - Percent-like metrics are decimal ratios, not formatted percentages.
  - `wape = 0.018` should display as `1.8%`.
  - `interval_coverage = 0.916` should display as `91.6%` or `91.7%`.
  - `raw_rows_received` is the raw row count accepted by Python.
  - `usable_rows` is the row count after weekly DIN-level preprocessing.
  - `rows_evaluated` is the number of backtest forecast-vs-actual rows, not the upload row count.
  - `ready_for_forecast` is true only when the summary passed the quality gate.
  - `model_path_counts` tells which forecast path was used during evaluation.
- Current model path values:
  - `prophet`: guarded Prophet ran successfully.
  - `fallback_recent_trend`: not enough weekly history for Prophet, so recent-demand/trend fallback was used.
  - `fallback_unsafe_prophet_output`: Prophet ran but produced unsafe values, so fallback replaced it.
- Migration notes:
  - No frontend migration; update API types once backend exposes this object.
- Backward compatibility notes:
  - Legacy uploads may not include `validation_summary.backtest`.

### Upload Readiness UI State

- Exact name: `UploadForecastReadinessState` recommended frontend type name.
- Fields:
  - `state: "NOT_RUN" | "RUNNING" | "READY" | "LOW_CONFIDENCE" | "FAILED" | "ERROR"`.
  - `backtest: BacktestReadiness | null`.
- Allowed values:
  - `NOT_RUN`: no backtest object.
  - `RUNNING`: backend upload/backtest status indicates in progress. Exact backend field is TO IMPLEMENT.
  - `READY`: `backtest.status = "PASS"`.
  - `LOW_CONFIDENCE`: `backtest.status = "LOW_CONFIDENCE"`.
  - `FAILED`: `backtest.status = "FAIL"`.
  - `ERROR`: `backtest.status = "ERROR"` or unknown state.
- Defaults:
  - Use `NOT_RUN` for missing data.
- Validation constraints:
  - Do not infer readiness from CSV upload success alone.
- Migration notes:
  - Requires backend to expose latest upload summary.
- Backward compatibility notes:
  - Existing pages should tolerate no readiness data.

## 5. Integration Contract

- Upstream dependencies: Spring Boot upload/readiness API, TO IMPLEMENT.
- Downstream dependencies: Python `POST /backtest/upload`, already implemented for backend use.
- Services called: frontend calls Spring Boot only.
- Endpoints hit: frontend endpoint path is UNDECIDED because Spring Boot API is not present in this repo.
- Events consumed: NOT IMPLEMENTED.
- Events published: NOT IMPLEMENTED.
- Files read or written: frontend must not read artifact files.
- Environment assumptions: frontend runs against Spring Boot API that includes latest CSV upload status and `validation_summary.backtest`.
- Auth assumptions: frontend uses existing authenticated session/API client.
- Retry behavior: frontend can refetch upload/readiness state while backend reports running/in-progress.
- Timeout behavior: if polling is added, stop or slow polling after a reasonable UI timeout; exact duration is UNDECIDED.
- Fallback behavior: if readiness is missing, show upload success separately from forecast readiness.
- Idempotency behavior: frontend should display the latest upload/backtest summary returned by backend.

## 6. Usage Instructions for Other Engineers

- Frontend can rely on the Python-produced summary fields once backend exposes them.
- Frontend should call Spring Boot, not Python.
- Frontend must handle `backtest` missing/null.
- Inputs frontend must provide: none beyond existing upload flow; Spring Boot triggers backtest.
- Outputs frontend will receive: upload status plus nested `validation_summary.backtest` once backend implements exposure.
- Loading states:
  - Uploading CSV.
  - Upload persisted, backtest running.
  - Backtest summary available.
- Empty states:
  - No upload.
  - Upload exists but no backtest summary.
- Success states:
  - `PASS`: show forecast-ready/trusted when `ready_for_forecast = true`.
  - `LOW_CONFIDENCE`: show forecast available with caution.
- Failure states:
  - `FAIL`: show not forecast-ready or low-quality data state.
  - `ERROR`: show backtest failed and allow retry/reupload path if backend provides one.
- Finalized:
  - Summary field names.
  - Python status values.
  - Decimal metric representation.
- Provisional:
  - Exact frontend route/page/component names.
  - Exact Spring Boot endpoint shape.
  - Exact display copy.
- Mocked or stubbed:
  - Frontend work is NOT IMPLEMENTED in this repo.
- Must not be changed without coordination:
  - Status value mapping.
  - Direct-browser calls to Python are forbidden.
  - Do not expose or depend on `artifact_path` in v1 UI.

## 7. Security and Authorization Notes

- Auth requirements: frontend must use existing authenticated Spring Boot API.
- Permission rules: Spring Boot must enforce organization/location ownership; frontend must not trust client-side filtering.
- Tenancy rules: display only the current tenant/location upload readiness returned by backend.
- Role checks: frontend should respect backend permissions for CSV upload/generate forecast actions.
- Data isolation: never cache or display readiness across tenants/locations.
- Sensitive fields: no `patient_id` should ever appear in this UI object.
- Sanitization: render metrics as plain text; do not render `error_message` as HTML.
- Forbidden fields: patient identifiers, raw upload rows, raw artifact file contents, Supabase keys.
- Logging restrictions: frontend analytics/logs should not include raw uploaded rows or patient identifiers.
- Compliance concerns: this is PHIPA/PIPEDA-sensitive workflow context; keep UI data scoped to aggregate backtest metrics only.

## 8. Environment and Configuration

- Spring Boot API base URL
  - Purpose: frontend source for upload/readiness state.
  - Required or optional: required by existing app.
  - Default behavior if missing: existing frontend API failure behavior.
  - Dev vs prod notes: exact env var is UNDECIDED because frontend code is not present in this repo.
- Python `POST /backtest/upload`
  - Purpose: internal backend-to-Python endpoint.
  - Required or optional: not directly configured in frontend.
  - Default behavior if missing: NOT APPLICABLE.
  - Dev vs prod notes: frontend must not call it directly.

## 9. Testing and Verification

- Tests added or updated in Python:
  - `tests/forecast_service/test_backtest_upload.py` covers the summary-producing endpoint.
- Frontend tests to add:
  - renders `PASS` as forecast-ready.
  - renders `LOW_CONFIDENCE` as caution state.
  - renders `FAIL` as not-ready/quality-gate failed.
  - renders `ERROR` as backtest failed.
  - renders missing `backtest` as not run or pending depending on upload status.
  - formats `wape` and `interval_coverage` decimal ratios as percentages.
- What was manually verified:
  - Python suite: `31 passed`.
- How to run Python tests:

```bash
python3 -m pytest
```

- How to locally validate frontend after backend implementation:
  - Upload `pharmaforecast_backtesting/pharmaforecast_test_dispensing_v2 copy.csv`.
  - Wait for backend backtest summary.
  - Confirm UI reads `validation_summary.backtest.status`.
  - Confirm `PASS` shows forecast-ready and metrics.
- Known gaps:
  - Frontend code is not present in this repo.
  - Spring Boot endpoint shape is not finalized in this repo.

## 10. Known Limitations and TODOs

- Frontend implementation remains to be built.
- Backend must expose upload/readiness summary before frontend can consume it.
- Exact UI copy is UNDECIDED.
- Exact polling or live update mechanism is UNDECIDED.
- Do not show detailed artifact links in v1.
- Do not block all forecasting UI solely on missing legacy backtest data unless product decides that migration behavior.
- Low-volume DIN details are not exposed in the summary; frontend gets location/upload-level readiness only.

## 11. Source of Truth Snapshot

- Final Python route: `POST /backtest/upload`.
- Final summary source for frontend: `validation_summary.backtest` from Spring Boot, TO IMPLEMENT.
- Final frontend status mapping:
  - `PASS` -> ready.
  - `LOW_CONFIDENCE` -> caution.
  - `FAIL` -> failed quality gate.
  - `ERROR` -> backtest error.
  - missing -> not run/pending.
- Final DTO/model names:
  - Recommended frontend type: `BacktestReadiness`.
  - Python DTO: `BacktestUploadSummary`.
- Final model path values:
  - `prophet`
  - `fallback_recent_trend`
  - `fallback_unsafe_prophet_output`
- Final key files:
  - `apps/forecast_service/app/schemas/backtest.py`
  - `apps/forecast_service/app/api/backtests.py`
  - `docs/contracts/frontend-upload-backtest-readiness.md`
- Breaking changes: none; this is new readiness metadata.

## 12. Copy-Paste Handoff for the Next Engineer

Python now produces upload-level backtest summaries, but frontend must wait for Spring Boot to expose the latest summary under upload/readiness data. The browser should never call Python `POST /backtest/upload` directly.

It is safe to depend on the summary fields and statuses in this contract. Frontend still needs to implement readiness states, metric formatting, and missing/pending/error handling once backend exposes `validation_summary.backtest`.

Read sections 3, 4, 6, and 7 first. The main traps are treating upload success as forecast readiness, formatting decimal metrics incorrectly, and exposing artifact paths or raw upload details in the UI.
