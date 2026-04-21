# Implementation Handoff Contract

## 1. Summary

- Implemented real Prophet-based numeric forecasting in the Python FastAPI forecast service.
- Added three forecast HTTP endpoints: `POST /forecast/drug`, `POST /forecast/batch`, and `POST /forecast/notification-check`.
- Added read-only Supabase access for `dispensing_records`.
- Added weekly demand aggregation, supplemental multi-location history merging, Ontario statutory holiday generation, Prophet model execution, forecast response calculation, reorder status calculation, batch SSE streaming, and notification alert filtering.
- Refactored forecast internals into deeper module boundaries: domain types, Supabase repository, demand history preparation, Prophet model runner, and orchestration engine.
- Why it was implemented: Spring Boot needs a numeric-only Python forecasting boundary that can generate drug demand forecasts on demand without mixing in LLM/Grok behavior.
- In scope: Python forecast service endpoints, request schemas, runtime dependencies, read-only Supabase integration, Prophet execution, SSE batch output, notification-check output, timeout behavior, and tests.
- Out of scope: Supabase writes, Spring Boot persistence, auth/authorization enforcement inside Python, inventory lookup for batch/notification calls, LLM explanations, Grok calls, chat behavior, purchase order text, external queues, and database migrations.
- Owner: `apps.forecast_service` owns the forecast API, orchestration, Prophet model execution, and Supabase read adapter.

## 2. Files Added or Changed

- `apps/forecast_service/app/api/__init__.py`: updated. Includes the forecast router alongside the existing health router.
- `apps/forecast_service/app/api/forecasts.py`: updated. Defines `POST /forecast/drug`, `POST /forecast/batch`, and `POST /forecast/notification-check`.
- `apps/forecast_service/app/schemas/forecast.py`: updated. Defines forecast request DTOs and validation constraints.
- `apps/forecast_service/app/services/domain.py`: created. Defines `ForecastingError`, `ForecastPrediction`, and `ForecastResult`.
- `apps/forecast_service/app/services/repository.py`: created. Defines the `DispensingRepository` protocol, cached Supabase client creation, and `SupabaseDispensingRepository`.
- `apps/forecast_service/app/services/history.py`: created. Defines date parsing, Monday week normalization, weekly total aggregation, supplemental history merging, and 30-day average daily demand calculation.
- `apps/forecast_service/app/services/model.py`: created. Defines the `ForecastModelRunner` protocol, `ProphetModelRunner`, Ontario holiday generation, Easter/Good Friday calculation, and Prophet output post-processing.
- `apps/forecast_service/app/services/forecasting.py`: created. Defines `ForecastEngine`, default engine construction, module-level route entrypoint functions, per-drug timeout handling, batch SSE generation, and notification alert filtering.
- `pyproject.toml`: updated. Adds runtime dependencies `numpy`, `pandas`, `prophet`, `python-dateutil`, and `supabase`.
- `requirements.txt`: updated. Adds runtime dependencies `numpy`, `pandas`, `prophet`, `python-dateutil`, and `supabase`.
- `tests/forecast_service/test_drug_forecast.py`: created. Adds endpoint and `ForecastEngine` boundary tests for insufficient data, operational metrics, SSE completion/error events, supplemental history merging, and notification alert output.
- `tests/forecast_service/test_foundation_structure.py`: updated. Changes the dependency guardrail from deferred Prophet to required Prophet for real forecasting.
- `docs/contracts/prophet-forecasting-real-implementation.md`: created. Source-of-truth implementation handoff contract for this feature.

## 3. Public Interface Contract

### `POST /forecast/drug`

- Name: `POST /forecast/drug`
- Type: HTTP endpoint
- Purpose: Generate a single numeric drug forecast for one `location_id` and `din`.
- Owner: `apps.forecast_service.app.api.forecasts.predict_drug`
- Inputs: JSON body validated by `DrugForecastRequest`.
- Outputs: Forecast JSON object on success, or structured error JSON for known forecast-domain failures.
- Required fields: `location_id`, `din`, `quantity_on_hand`.
- Optional fields: `horizon_days`, `lead_time_days`, `safety_multiplier`, `supplemental_history`.
- Validation rules: `horizon_days` must be one of `7`, `14`, or `30`; `quantity_on_hand` must be `>= 0`; `lead_time_days` must be `>= 1`; `safety_multiplier` must be one of `1.5`, `1.0`, or `0.75`; each supplemental history item must have `quantity >= 0`.
- Defaults: `horizon_days=7`, `lead_time_days=2`, `safety_multiplier=1.0`, `supplemental_history=None`.
- Status codes or result states: `200 OK` for successful forecasts and structured domain errors; FastAPI returns validation errors for invalid request bodies.
- Error shapes: insufficient data returns `{"error": "insufficient_data", "minimum_rows": 14, "confidence": "LOW"}`; timeout returns `{"error": "forecast_timeout", "confidence": "LOW"}`; missing Supabase configuration raises `ForecastingError("supabase_not_configured")` and is not converted to a custom HTTP error shape.
- Example input:

```json
{
  "location_id": "11111111-1111-1111-1111-111111111111",
  "din": "12345678",
  "horizon_days": 14,
  "quantity_on_hand": 30,
  "lead_time_days": 2,
  "safety_multiplier": 1.0,
  "supplemental_history": [
    {
      "week": "2026-03-02",
      "quantity": 5
    }
  ]
}
```

- Example output:

```json
{
  "din": "12345678",
  "location_id": "11111111-1111-1111-1111-111111111111",
  "horizon_days": 14,
  "predicted_quantity": 21,
  "prophet_lower": 18,
  "prophet_upper": 24,
  "confidence": "MEDIUM",
  "days_of_supply": 15.0,
  "avg_daily_demand": 2.0,
  "reorder_status": "GREEN",
  "reorder_point": 4.0,
  "generated_at": "2026-04-20T00:00:00+00:00",
  "data_points_used": 30
}
```

### `POST /forecast/batch`

- Name: `POST /forecast/batch`
- Type: HTTP endpoint returning Server-Sent Events.
- Purpose: Run forecasts concurrently for multiple DINs and stream per-DIN completion/error events.
- Owner: `apps.forecast_service.app.api.forecasts.predict_batch`
- Inputs: JSON body validated by `BatchForecastRequest`.
- Outputs: `text/event-stream` response where each event is formatted as `data: <json>\n\n`.
- Required fields: `location_id`, `dins`, `horizon_days`, `thresholds`.
- Optional fields: individual DIN threshold entries may be omitted from `thresholds`; omitted thresholds default inside orchestration.
- Validation rules: `dins` must contain at least one item; `horizon_days` must be one of `7`, `14`, or `30`; each threshold `lead_time_days` must be `>= 1`; each threshold `safety_multiplier` must be one of `1.5`, `1.0`, or `0.75`.
- Defaults: missing per-DIN threshold defaults to `lead_time_days=2` and `safety_multiplier=1.0`; batch-generated individual forecasts use `quantity_on_hand=0` and `supplemental_history=None`.
- Status codes or result states: `200 OK` with SSE stream; each DIN event has `status` equal to `"complete"` or `"error"`; final event has `status` equal to `"done"`.
- Error shapes: per-DIN structured error event is `{"din": "<din>", "status": "error", "error": "<message>"}`; final summary event is `{"status": "done", "total": <int>, "succeeded": <int>, "failed": <int>}`.
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
    },
    "22222222": {
      "lead_time_days": 2,
      "safety_multiplier": 1.0
    }
  }
}
```

- Example output:

```text
data: {"din":"11111111","status":"complete","result":{"din":"11111111","location_id":"11111111-1111-1111-1111-111111111111","horizon_days":7,"predicted_quantity":10,"prophet_lower":8,"prophet_upper":12,"confidence":"HIGH","days_of_supply":0.0,"avg_daily_demand":2.0,"reorder_status":"RED","reorder_point":4.0,"generated_at":"2026-04-20T00:00:00+00:00","data_points_used":30}}

data: {"din":"22222222","status":"error","error":"insufficient_data"}

data: {"status":"done","total":2,"succeeded":1,"failed":1}
```

### `POST /forecast/notification-check`

- Name: `POST /forecast/notification-check`
- Type: HTTP endpoint.
- Purpose: Run forecasts for all distinct DINs for a location and return only actionable reorder alerts.
- Owner: `apps.forecast_service.app.api.forecasts.predict_notification_check`
- Inputs: JSON body validated by `NotificationCheckRequest`.
- Outputs: JSON object with `alerts`.
- Required fields: `location_id`.
- Optional fields: none.
- Validation rules: `location_id` must be present as a string.
- Defaults: individual forecasts use `horizon_days=7`, `quantity_on_hand=0`, `lead_time_days=2`, `safety_multiplier=1.0`, and `supplemental_history=None`.
- Status codes or result states: `200 OK` with `alerts`; only `RED` and `AMBER` forecasts are included.
- Error shapes: NOT IMPLEMENTED as a custom shape; unhandled exceptions use FastAPI default error handling.
- Example input:

```json
{
  "location_id": "11111111-1111-1111-1111-111111111111"
}
```

- Example output:

```json
{
  "alerts": [
    {
      "din": "11111111",
      "reorder_status": "RED",
      "days_of_supply": 2.0,
      "predicted_quantity": 10
    }
  ]
}
```

### `ForecastEngine`

- Name: `ForecastEngine`
- Type: Python class.
- Purpose: Deep module boundary that owns forecast orchestration across repository reads, demand history preparation, model execution, timeout handling, batch streaming, and notification filtering.
- Owner: `apps.forecast_service.app.services.forecasting`.
- Inputs: constructor accepts `repository: DispensingRepository`, `model_runner: ForecastModelRunner`, optional `history_preparer: DemandHistoryPreparer`, and optional `timeout_seconds: int`.
- Outputs: dictionaries matching the public forecast response shapes, and SSE event strings for batch.
- Required fields: `repository`, `model_runner`.
- Optional fields: `history_preparer`, `timeout_seconds`.
- Validation rules: request validation is handled by Pydantic DTOs before route entry; `ForecastEngine` assumes typed request objects.
- Defaults: `history_preparer=DemandHistoryPreparer()`, `timeout_seconds=30`.
- Status codes or result states: not an HTTP interface; returns success dictionaries or structured error dictionaries.
- Error shapes: same domain error dictionaries as route functions for insufficient data and timeout.
- Example input:

```python
engine = ForecastEngine(
    repository=SupabaseDispensingRepository(),
    model_runner=ProphetModelRunner(),
)
result = engine.forecast_drug(request)
```

- Example output:

```python
{
    "din": "12345678",
    "location_id": "11111111-1111-1111-1111-111111111111",
    "horizon_days": 14,
    "predicted_quantity": 21,
    "prophet_lower": 18,
    "prophet_upper": 24,
    "confidence": "MEDIUM",
    "days_of_supply": 15.0,
    "avg_daily_demand": 2.0,
    "reorder_status": "GREEN",
    "reorder_point": 4.0,
    "generated_at": "2026-04-20T00:00:00+00:00",
    "data_points_used": 30,
}
```

### Module-Level Forecast Functions

- Name: `forecast_drug`, `batch_forecast`, `notification_check`.
- Type: exported Python functions.
- Purpose: Route-facing functions that delegate to the process-wide default `ForecastEngine`.
- Owner: `apps.forecast_service.app.services.forecasting`.
- Inputs: `DrugForecastRequest`, `BatchForecastRequest`, or `NotificationCheckRequest`.
- Outputs: same as the matching `ForecastEngine` methods.
- Required fields: request object required.
- Optional fields: none at function level.
- Validation rules: request DTO validation happens before function invocation in FastAPI.
- Defaults: use `get_default_engine()`, which lazily constructs an engine with `SupabaseDispensingRepository` and `ProphetModelRunner`.
- Status codes or result states: not HTTP interfaces directly.
- Error shapes: same as `ForecastEngine`.
- Example input: `forecast_drug(request)`.
- Example output: forecast dictionary or structured error dictionary.

### `GET /health`

- Name: `GET /health`
- Type: HTTP endpoint.
- Purpose: Existing health check for the forecast service.
- Owner: `apps.forecast_service.app.api.health`.
- Inputs: none.
- Outputs: `{"status": "ok"}`.
- Required fields: none.
- Optional fields: none.
- Validation rules: none.
- Defaults: always returns `"ok"`.
- Status codes or result states: `200 OK`.
- Error shapes: NOT IMPLEMENTED as a custom shape.
- Example input: `GET /health`.
- Example output:

```json
{
  "status": "ok"
}
```

## 4. Data Contract

### `DrugForecastRequest`

- Exact name: `DrugForecastRequest`.
- Fields: `location_id`, `din`, `horizon_days`, `quantity_on_hand`, `lead_time_days`, `safety_multiplier`, `supplemental_history`.
- Field types: `location_id: str`, `din: str`, `horizon_days: Literal[7, 14, 30]`, `quantity_on_hand: int`, `lead_time_days: int`, `safety_multiplier: Literal[1.5, 1.0, 0.75]`, `supplemental_history: Optional[list[SupplementalHistoryPoint]]`.
- Required vs optional: `location_id`, `din`, and `quantity_on_hand` are required; the other fields have defaults or may be `None`.
- Allowed values: `horizon_days` allows `7`, `14`, `30`; `safety_multiplier` allows `1.5`, `1.0`, `0.75`.
- Defaults: `horizon_days=7`, `lead_time_days=2`, `safety_multiplier=1.0`, `supplemental_history=None`.
- Validation constraints: `quantity_on_hand >= 0`; `lead_time_days >= 1`; `SupplementalHistoryPoint.quantity >= 0`.
- Migration notes: replaces provisional placeholder-only forecast schema with real request DTOs.
- Backward compatibility notes: `ForecastPlaceholder` remains in the file but is still provisional and should not be used as a forecast contract.

### `SupplementalHistoryPoint`

- Exact name: `SupplementalHistoryPoint`.
- Fields: `week`, `quantity`.
- Field types: `week: str`, `quantity: int`.
- Required vs optional: both fields are required.
- Allowed values: `week` must be parseable by `datetime.fromisoformat` after replacing trailing `Z` with `+00:00`; `quantity` must be `>= 0`.
- Defaults: none.
- Validation constraints: `quantity >= 0`.
- Migration notes: introduced for multi-location demand signal support.
- Backward compatibility notes: no previous finalized supplemental history DTO existed.

### `ForecastThreshold`

- Exact name: `ForecastThreshold`.
- Fields: `lead_time_days`, `safety_multiplier`.
- Field types: `lead_time_days: int`, `safety_multiplier: Literal[1.5, 1.0, 0.75]`.
- Required vs optional: both fields are optional in the model because defaults are provided.
- Allowed values: `safety_multiplier` allows `1.5`, `1.0`, `0.75`.
- Defaults: `lead_time_days=2`, `safety_multiplier=1.0`.
- Validation constraints: `lead_time_days >= 1`.
- Migration notes: introduced for batch forecasting.
- Backward compatibility notes: no previous finalized threshold DTO existed.

### `BatchForecastRequest`

- Exact name: `BatchForecastRequest`.
- Fields: `location_id`, `dins`, `horizon_days`, `thresholds`.
- Field types: `location_id: str`, `dins: list[str]`, `horizon_days: Literal[7, 14, 30]`, `thresholds: Dict[str, ForecastThreshold]`.
- Required vs optional: all fields are required.
- Allowed values: `horizon_days` allows `7`, `14`, `30`.
- Defaults: no field defaults at the request level.
- Validation constraints: `dins` must have at least one item; nested `ForecastThreshold` validation applies.
- Migration notes: introduced for SSE batch forecasting.
- Backward compatibility notes: no previous finalized batch request DTO existed.

### `NotificationCheckRequest`

- Exact name: `NotificationCheckRequest`.
- Fields: `location_id`.
- Field types: `location_id: str`.
- Required vs optional: required.
- Allowed values: any string accepted by Pydantic.
- Defaults: none.
- Validation constraints: `location_id` must be present.
- Migration notes: introduced for scheduled Spring Boot notification checks.
- Backward compatibility notes: no previous finalized notification-check request DTO existed.

### `ForecastPrediction`

- Exact name: `ForecastPrediction`.
- Fields: `predicted_quantity`, `prophet_lower`, `prophet_upper`, `confidence`.
- Field types: `predicted_quantity: int`, `prophet_lower: int`, `prophet_upper: int`, `confidence: str`.
- Required vs optional: all fields are required.
- Allowed values: `confidence` is calculated as `"HIGH"`, `"MEDIUM"`, or `"LOW"` by `ProphetModelRunner`.
- Defaults: none.
- Validation constraints: dataclass only; no runtime validation is applied.
- Migration notes: introduced as the model-runner output boundary.
- Backward compatibility notes: internal Python type, not an HTTP DTO.

### `ForecastResult`

- Exact name: `ForecastResult`.
- Fields: `din`, `location_id`, `horizon_days`, `predicted_quantity`, `prophet_lower`, `prophet_upper`, `confidence`, `days_of_supply`, `avg_daily_demand`, `reorder_status`, `reorder_point`, `generated_at`, `data_points_used`.
- Field types: `din: str`, `location_id: str`, `horizon_days: int`, `predicted_quantity: int`, `prophet_lower: int`, `prophet_upper: int`, `confidence: str`, `days_of_supply: float`, `avg_daily_demand: float`, `reorder_status: str`, `reorder_point: float`, `generated_at: str`, `data_points_used: int`.
- Required vs optional: all fields are required.
- Allowed values: `confidence` is `"HIGH"`, `"MEDIUM"`, or `"LOW"`; `reorder_status` is `"GREEN"`, `"AMBER"`, or `"RED"`.
- Defaults: none.
- Validation constraints: dataclass only; no runtime validation is applied.
- Migration notes: introduced as the internal representation of the public forecast response.
- Backward compatibility notes: public response dictionary is produced with `ForecastResult(...).__dict__`.

### Forecast Success JSON Shape

- Exact name: forecast success response.
- Fields: `din`, `location_id`, `horizon_days`, `predicted_quantity`, `prophet_lower`, `prophet_upper`, `confidence`, `days_of_supply`, `avg_daily_demand`, `reorder_status`, `reorder_point`, `generated_at`, `data_points_used`.
- Field types: same as `ForecastResult`.
- Required vs optional: all fields are present on success.
- Allowed values: `confidence` is `"HIGH"`, `"MEDIUM"`, or `"LOW"`; `reorder_status` is `"GREEN"`, `"AMBER"`, or `"RED"`.
- Defaults: none.
- Validation constraints: quantities returned by `ProphetModelRunner` are integers; `predicted_quantity` and `prophet_lower` are clamped at zero; `prophet_upper` is rounded to an integer but is not clamped.
- Migration notes: new public response shape for real forecasting.
- Backward compatibility notes: replaces placeholder forecast readiness behavior.

### Insufficient Data JSON Shape

- Exact name: insufficient data response.
- Fields: `error`, `minimum_rows`, `confidence`.
- Field types: `error: str`, `minimum_rows: int`, `confidence: str`.
- Required vs optional: all fields are required.
- Allowed values: `error="insufficient_data"`, `minimum_rows=14`, `confidence="LOW"`.
- Defaults: fixed values from `build_insufficient_data_response()`.
- Validation constraints: returned before Prophet is called when primary Supabase rows are fewer than `14`.
- Migration notes: new structured domain error.
- Backward compatibility notes: callers must handle this response as a successful HTTP response with an error payload.

### Batch SSE Event Shapes

- Exact name: batch SSE events.
- Fields: complete event has `din`, `status`, `result`; error event has `din`, `status`, `error`; final event has `status`, `total`, `succeeded`, `failed`.
- Field types: `din: str`, `status: str`, `result: object`, `error: str`, `total: int`, `succeeded: int`, `failed: int`.
- Required vs optional: fields vary by event type.
- Allowed values: per-DIN `status` is `"complete"` or `"error"`; final `status` is `"done"`.
- Defaults: none.
- Validation constraints: SSE lines are emitted as `data: <compact-json>\n\n`.
- Migration notes: introduced for batch forecasting.
- Backward compatibility notes: ordering of per-DIN events is completion-order dependent because `as_completed()` is used.

### Supabase `dispensing_records` Read Shape

- Exact name: `dispensing_records` query shape.
- Fields consumed for single-drug history: `dispensed_date`, `quantity_dispensed`.
- Fields consumed for distinct DIN lookup: `din`.
- Field types expected by code: `dispensed_date` parseable as date/datetime/ISO string; `quantity_dispensed` numeric; `din` string.
- Required vs optional: fields are required for rows returned by the selected query.
- Allowed values: NOT SPECIFIED beyond parseability/numeric conversion.
- Defaults: none.
- Validation constraints: no explicit row-level Pydantic validation is implemented.
- Migration notes: no database migration was added.
- Backward compatibility notes: `patient_id` is not selected or consumed.

## 5. Integration Contract

- Upstream dependencies: Spring Boot or another trusted caller sends HTTP requests to the forecast service; Supabase contains `dispensing_records` data for the requested `location_id` and `din`.
- Downstream dependencies: Supabase is called read-only through `supabase-py`; Prophet is executed in-process.
- Services called: Supabase only.
- Endpoints hit: Supabase table API through `client.table("dispensing_records")`; no external HTTP endpoints are manually constructed in this code.
- Events consumed: NOT IMPLEMENTED.
- Events published: NOT IMPLEMENTED.
- Files read or written: Pydantic settings may read `.env`; no forecast endpoint writes files; this contract file is written as documentation.
- Environment assumptions: `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are required for forecast endpoints that use the default `SupabaseDispensingRepository`; they are not required for app import or `GET /health`.
- Auth assumptions: Python forecast service does not authenticate users or validate tenant ownership. Spring Boot remains responsible for authentication, authorization, organization/location ownership checks, and deciding when to call this service.
- Retry behavior: NOT IMPLEMENTED.
- Timeout behavior: `ForecastEngine.forecast_drug()` uses a single-worker `ThreadPoolExecutor` and waits `30` seconds by default. On timeout it returns `{"error": "forecast_timeout", "confidence": "LOW"}` and shuts down the executor with `wait=False` and `cancel_futures=True`.
- Fallback behavior: insufficient primary rows return the structured insufficient-data response; missing per-DIN batch thresholds default to `lead_time_days=2` and `safety_multiplier=1.0`; batch and notification forecasts default `quantity_on_hand=0` because their request contracts do not include inventory.
- Idempotency behavior: all forecast endpoints are read-only from the service perspective; repeated calls may return different forecasts if Supabase data changes or if Prophet behavior changes across dependency versions.

## 6. Usage Instructions for Other Engineers

- Use `POST /forecast/drug` when Spring Boot needs a single drug forecast and can provide `quantity_on_hand`.
- Use `POST /forecast/batch` when Spring Boot needs to forecast multiple DINs and stream progress to a caller; handle per-DIN `"complete"` and `"error"` events plus the final `"done"` event.
- Use `POST /forecast/notification-check` for the daily scheduled notification scan; persist notifications in Spring Boot, not in the Python service.
- Import `ForecastEngine` for tests or future orchestration changes that need dependency injection.
- Inject a `DispensingRepository` and `ForecastModelRunner` into `ForecastEngine` when testing or replacing external dependencies.
- Import `SupabaseDispensingRepository` only when production code should read from Supabase.
- Import `ProphetModelRunner` only when real Prophet execution is desired.
- Provide `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` before calling forecast endpoints in a real runtime environment.
- Handle loading states: batch endpoint streams SSE events as each DIN completes; single-drug and notification-check endpoints return ordinary JSON responses.
- Handle empty states: insufficient data returns `{"error": "insufficient_data", "minimum_rows": 14, "confidence": "LOW"}`; notification-check can return `{"alerts": []}`.
- Handle success states: single-drug success returns all forecast fields; batch success event wraps the forecast in `result`; notification-check success returns actionable `alerts`.
- Handle failure states: validation errors are FastAPI-managed; structured domain errors use HTTP 200 with an `error` field; missing Supabase config is not converted to a custom HTTP response.
- Finalized: route names, request DTO names, success response fields, insufficient-data error shape, SSE event shapes, confidence values, and reorder status values.
- Provisional: `ForecastPlaceholder` and `ForecastService.ready()` remain placeholders from the foundation and should not be used for real forecast integrations.
- MOCKED: tests use `_FakeRepository`, `_FakeModelRunner`, and `_FakeEndpointEngine` inside `tests/forecast_service/test_drug_forecast.py`.
- Do not change `/health`, `apps.forecast_service.app.main:app`, no-write-to-Supabase behavior, or the no-LLM boundary without coordination.

## 7. Security and Authorization Notes

- The forecast service reads Supabase with `SUPABASE_SERVICE_KEY`, so callers must treat the Python service as a trusted backend service.
- The Python forecast service does not enforce user auth, role checks, organization ownership, or location ownership.
- Spring Boot must validate organization/location ownership server-side before calling the forecast service.
- Supabase RLS must not be the only isolation control; this service uses a service key.
- `patient_id` is not selected from Supabase, not sent to Prophet, not returned in responses, and not logged by this implementation.
- No LLM/Grok/chat/prompt/explanation logic exists in `apps/forecast_service`.
- Forecast logs include `din`, `location_id`, `horizon_days`, `duration_ms`, and `data_points_used`; logs must not be extended to include `patient_id`.
- The service sends only numeric aggregated weekly `ds`/`y` history to Prophet in-process. No LLM or external AI API receives pharmacy data.
- Data residency for Supabase and hosting must be handled by deployment configuration; this code does not enforce region selection.

## 8. Environment and Configuration

### `SUPABASE_URL`

- Exact name: `SUPABASE_URL`.
- Purpose: Supabase project URL used by `get_supabase_client()`.
- Required or optional: optional for app import and `GET /health`; required for real forecast endpoints using the default engine.
- Default behavior if missing: `shared.config.settings.Settings.supabase_url` is `None`; forecast calls through `SupabaseDispensingRepository` raise `ForecastingError("supabase_not_configured")`.
- Dev vs prod notes: local tests do not require it because they inject fake repositories; deployed forecast runtime must provide it.

### `SUPABASE_SERVICE_KEY`

- Exact name: `SUPABASE_SERVICE_KEY`.
- Purpose: Supabase service key used by `get_supabase_client()`.
- Required or optional: optional for app import and `GET /health`; required for real forecast endpoints using the default engine.
- Default behavior if missing: `shared.config.settings.Settings.supabase_service_key` is `None`; forecast calls through `SupabaseDispensingRepository` raise `ForecastingError("supabase_not_configured")`.
- Dev vs prod notes: local tests do not require it because they inject fake repositories; deployed forecast runtime must provide it and protect it as a secret.

### `PORT`

- Exact name: `PORT`.
- Purpose: Runtime port setting from the forecast foundation.
- Required or optional: optional.
- Default behavior if missing: defaults to `8000`.
- Dev vs prod notes: Dockerfile uses `${PORT:-8000}` for Uvicorn.

### `FORECAST_TIMEOUT_SECONDS`

- Exact name: `FORECAST_TIMEOUT_SECONDS`.
- Purpose: Python module constant controlling default per-drug forecast timeout.
- Required or optional: not an environment variable.
- Default behavior if missing: constant is `30`.
- Dev vs prod notes: tests can inject a different `timeout_seconds` through `ForecastEngine`.

## 9. Testing and Verification

- Tests added: `tests/forecast_service/test_drug_forecast.py`.
- Tests updated: `tests/forecast_service/test_foundation_structure.py`.
- Test coverage includes insufficient-data response, single-drug operational metrics, batch SSE complete/error events, structured batch domain errors, supplemental history merging before model execution, notification-check alert output, dependency guardrails, service boundary guardrails, config behavior, and health endpoint behavior.
- Tests use fakes instead of live Supabase or live Prophet where appropriate: `_FakeRepository`, `_FakeModelRunner`, and `_FakeEndpointEngine`.
- Manual verification command run: `python3 -m pytest`.
- Latest observed verification result: `13 passed in 0.24s` and `13 passed in 0.27s`.
- How to run tests: from `/Users/adamsaleh/Downloads/pharmacast-ai`, run `python3 -m pytest`.
- How to locally validate the feature against real dependencies: install runtime dependencies from `requirements.txt`, set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`, start `uvicorn apps.forecast_service.app.main:app --host 0.0.0.0 --port 8000`, and call `POST /forecast/drug` with a DIN/location that has at least 14 `dispensing_records` rows.
- Known gaps in test coverage: no live Prophet fit test, no live Supabase integration test, no explicit timeout test, no FastAPI validation-error snapshot test, and no production Docker build test after adding Prophet.

## 10. Known Limitations and TODOs

- Batch forecasts use `quantity_on_hand=0` because `BatchForecastRequest` does not include inventory quantities.
- Notification-check forecasts use `quantity_on_hand=0` because `NotificationCheckRequest` does not include inventory quantities and the service does not query inventory separately.
- Missing Supabase configuration is raised as `ForecastingError("supabase_not_configured")` and is not converted to a custom HTTP JSON error response.
- `ProphetModelRunner` uses `model.make_future_dataframe(periods=horizon_weeks, freq="W")`; this follows the requested `freq="W"` but may not align to Monday even though historical aggregation uses Monday week starts.
- `avg_daily_demand` is calculated as total quantity over the last 30 calendar days divided by `30.0`, not as mean over dispensing days only.
- `prophet_upper` is rounded to an integer but is not clamped at zero.
- No retry behavior exists for Supabase reads.
- No cancellation guarantee exists for already-running Prophet work after a timeout; the executor shuts down with `wait=False` and requests cancellation for pending futures.
- No database writes are implemented by design; Spring Boot owns persistence.
- No auth is implemented by design; Spring Boot owns auth and ownership checks.
- No LLM/Grok behavior is implemented by design; `apps/llm_service` remains the language boundary.
- Follow-up task: extend batch and notification request/lookup contracts to supply real `quantity_on_hand`.
- Follow-up task: add integration tests with a local or test Supabase-compatible data source if the project adds one.
- Follow-up task: decide whether forecast weekly frequency should be `W` or `W-MON`.

## 11. Source of Truth Snapshot

- Final route names: `GET /health`, `POST /forecast/drug`, `POST /forecast/batch`, `POST /forecast/notification-check`.
- Final DTO/model names: `DrugForecastRequest`, `SupplementalHistoryPoint`, `ForecastThreshold`, `BatchForecastRequest`, `NotificationCheckRequest`, `ForecastPrediction`, `ForecastResult`.
- Final service interfaces: `ForecastEngine`, `DispensingRepository`, `ForecastModelRunner`, `DemandHistoryPreparer`, `SupabaseDispensingRepository`, `ProphetModelRunner`.
- Final module-level route functions: `forecast_drug`, `batch_forecast`, `notification_check`.
- Final confidence values: `"HIGH"`, `"MEDIUM"`, `"LOW"`.
- Final reorder status values: `"GREEN"`, `"AMBER"`, `"RED"`.
- Final batch SSE statuses: `"complete"`, `"error"`, `"done"`.
- Final key files: `apps/forecast_service/app/api/forecasts.py`, `apps/forecast_service/app/schemas/forecast.py`, `apps/forecast_service/app/services/forecasting.py`, `apps/forecast_service/app/services/repository.py`, `apps/forecast_service/app/services/history.py`, `apps/forecast_service/app/services/model.py`, `apps/forecast_service/app/services/domain.py`.
- Breaking changes from previous version: `apps/forecast_service/app/api/forecasts.py` changed from a non-included placeholder router at prefix `/forecasts` to an included real router at prefix `/forecast`; `prophet` is now a required runtime dependency instead of deferred.

## 12. Copy-Paste Handoff for the Next Engineer

Real numeric Prophet forecasting is implemented in `apps.forecast_service` with three public endpoints: `POST /forecast/drug`, `POST /forecast/batch`, and `POST /forecast/notification-check`. The implementation is read-only against Supabase, uses `ProphetModelRunner` for in-process forecasting, and keeps LLM/Grok behavior out of the forecast service.

It is safe to depend on the route names, request DTOs, forecast success fields, insufficient-data error shape, SSE event shapes, confidence values, reorder status values, and the `ForecastEngine` dependency-injection boundary. Use fake `DispensingRepository` and `ForecastModelRunner` implementations for tests instead of patching internals.

What remains to be built: real inventory input for batch and notification-check flows, custom HTTP error handling for missing Supabase configuration, live Supabase/Prophet integration tests, and a decision on `freq="W"` versus `freq="W-MON"`. The main gotcha is that batch and notification currently pass `quantity_on_hand=0`, so their `days_of_supply` and reorder alerts are conservative until Spring Boot provides inventory context.
