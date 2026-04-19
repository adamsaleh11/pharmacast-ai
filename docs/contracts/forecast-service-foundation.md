# Implementation Handoff Contract

## 1. Summary
- Implemented the PharmaForecast shared Python service foundation in `/Users/adamsaleh/Downloads/pharmacast-ai`.
- Implemented a dedicated FastAPI forecast service scaffold under `apps/forecast_service`.
- Implemented one public forecast service endpoint: `GET /health`.
- Implemented root Python project metadata, runtime requirements, development requirements, shared configuration, shared JSON logging, placeholder forecast API/schema/service modules, an `apps/llm_service` boundary placeholder, and a forecast-service-specific Dockerfile.
- Implemented behavior tests for the health endpoint, configuration defaults/env overrides, service boundary directories, no language-generation concerns in forecast service source, deferred Prophet dependency, and Dockerfile command shape.
- Why it was implemented: future Spring Boot forecast orchestration needs a deployable Python numeric-forecasting boundary that is separate from the future LLM service.
- In scope: Python repo structure, FastAPI forecast app, health endpoint, config management, logging setup, placeholder modules, dependencies, Dockerfile, PRD, plan, tests, and this contract.
- Out of scope: real forecasting logic, Prophet dependency, forecast request/response API, database reads, database writes, Supabase client implementation, Spring Boot integration, LLM service implementation, chat behavior, explanation behavior, prompt construction, Grok client code, purchase order drafting, auth, authorization, and Fly.io configuration.
- Owner: Python forecast service foundation in `apps.forecast_service`; shared helpers in `shared`.

## 2. Files Added or Changed
- `docs/prd/forecast-service-foundation.md`: created. Product requirements document for the forecast service foundation.
- `plans/forecast-service-foundation.md`: created. Tracer-bullet implementation plan for the forecast service foundation.
- `docs/contracts/forecast-service-foundation.md`: created. This implementation handoff contract.
- `pyproject.toml`: created. Defines project metadata for `pharmacast-ai`, Python requirement `>=3.9`, runtime dependencies, optional test dependencies, setuptools build backend, and pytest configuration.
- `requirements.txt`: created. Runtime dependency file for Docker and local installs. Includes `fastapi`, `pydantic-settings`, and `uvicorn[standard]`.
- `requirements-dev.txt`: created. Development/test dependency file. Includes `requirements.txt`, `httpx`, and `pytest`.
- `apps/__init__.py`: created. Marks `apps` as an importable package.
- `apps/forecast_service/__init__.py`: created. Marks the forecast service package.
- `apps/forecast_service/Dockerfile`: created. Builds and runs the forecast service independently with `uvicorn apps.forecast_service.app.main:app`.
- `apps/forecast_service/app/__init__.py`: created. Marks the FastAPI forecast app package.
- `apps/forecast_service/app/main.py`: created. Creates `FastAPI(title="PharmaForecast Forecast Service")`, configures logging, and includes the forecast service API router.
- `apps/forecast_service/app/api/__init__.py`: created. Defines the root `APIRouter` and includes the health router.
- `apps/forecast_service/app/api/health.py`: created. Implements `GET /health`.
- `apps/forecast_service/app/api/forecasts.py`: created. Placeholder forecast router with prefix `/forecasts` and tag `forecasts`; it is not included in the app and exposes no route.
- `apps/forecast_service/app/schemas/__init__.py`: created. Marks forecast service schema package.
- `apps/forecast_service/app/schemas/health.py`: created. Defines `HealthResponse`.
- `apps/forecast_service/app/schemas/forecast.py`: created. Defines provisional `ForecastPlaceholder` with `ready: bool = False`.
- `apps/forecast_service/app/services/__init__.py`: created. Marks forecast service domain operations package.
- `apps/forecast_service/app/services/forecast_service.py`: created. Defines provisional `ForecastService.ready()` returning `False`.
- `apps/llm_service/__init__.py`: created. Marks a future standalone language service package boundary. No LLM behavior is implemented.
- `shared/__init__.py`: created. Marks shared helper package.
- `shared/config/__init__.py`: created. Marks shared config package.
- `shared/config/settings.py`: created. Defines `Settings`, `load_settings()`, and `cached_settings()`.
- `shared/logging/__init__.py`: created. Marks shared logging package.
- `shared/logging/setup.py`: created. Defines `JsonFormatter` and `configure_logging()`.
- `shared/utils/__init__.py`: created. Marks shared utility package.
- `tests/forecast_service/test_health.py`: created. Verifies `GET /health` returns HTTP 200 and `{"status": "ok"}`.
- `tests/forecast_service/test_config.py`: created. Verifies config defaults and environment overrides.
- `tests/forecast_service/test_foundation_structure.py`: created. Verifies service boundaries, separation guardrails, deferred Prophet dependency, and Dockerfile command shape.

## 3. Public Interface Contract

### `GET /health`
- Name: `GET /health`
- Type: HTTP endpoint
- Purpose: Lightweight health check for local development, container runtime checks, and deployment health checks.
- Owner: `apps.forecast_service.app.api.health`
- Inputs: none
- Outputs: JSON object with `status`
- Required fields: none
- Optional fields: none
- Validation rules: none
- Defaults: `status` is always `"ok"`
- Status codes or result states: `200 OK` on success
- Error shapes: NOT IMPLEMENTED; no custom error shape was added for this endpoint
- Example input: `GET /health`
- Example output:
```json
{
  "status": "ok"
}
```

### ASGI App `apps.forecast_service.app.main:app`
- Name: `apps.forecast_service.app.main:app`
- Type: FastAPI ASGI application
- Purpose: Import path for local runs, tests, Docker, and future deployment.
- Owner: `apps/forecast_service/app/main.py`
- Inputs: ASGI HTTP requests
- Outputs: FastAPI HTTP responses
- Required fields: none
- Optional fields: runtime environment can provide `PORT`, `SUPABASE_URL`, and `SUPABASE_SERVICE_KEY`
- Validation rules: FastAPI route validation only; no business payload validation is implemented
- Defaults: application title is `"PharmaForecast Forecast Service"`
- Status codes or result states: app imports and serves included routes
- Error shapes: FastAPI-managed errors only; custom errors are NOT IMPLEMENTED
- Example input: `uvicorn apps.forecast_service.app.main:app --host 0.0.0.0 --port 8000`
- Example output: running ASGI app serving `GET /health`

### Function `load_settings()`
- Name: `load_settings`
- Type: exported Python function
- Purpose: Load service settings from environment variables and `.env`.
- Owner: `shared.config.settings`
- Inputs: process environment and optional `.env` file
- Outputs: `Settings`
- Required fields: none
- Optional fields: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `PORT`
- Validation rules: `PORT` must be parseable as an integer if provided
- Defaults: `port=8000`, `supabase_url=None`, `supabase_service_key=None`
- Status codes or result states: returns a new `Settings` instance
- Error shapes: Pydantic settings validation errors for invalid field types
- Example input:
```bash
PORT=9000 SUPABASE_URL=https://example.supabase.co SUPABASE_SERVICE_KEY=service-key
```
- Example output:
```python
Settings(
    port=9000,
    supabase_url="https://example.supabase.co",
    supabase_service_key="service-key",
)
```

### Function `cached_settings()`
- Name: `cached_settings`
- Type: exported Python function
- Purpose: Return a cached `Settings` instance for runtime callers that do not need per-call env reload behavior.
- Owner: `shared.config.settings`
- Inputs: process environment and optional `.env` file on first call
- Outputs: `Settings`
- Required fields: none
- Optional fields: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `PORT`
- Validation rules: same as `load_settings()`
- Defaults: same as `load_settings()`
- Status codes or result states: first call loads settings; later calls return the cached instance
- Error shapes: Pydantic settings validation errors for invalid field types on first load
- Example input: `cached_settings()`
- Example output: `Settings(port=8000, supabase_url=None, supabase_service_key=None)` when no relevant env vars are set

### Function `configure_logging(level=logging.INFO)`
- Name: `configure_logging`
- Type: exported Python function
- Purpose: Initialize root logging with JSON-formatted log output.
- Owner: `shared.logging.setup`
- Inputs: optional Python logging level integer
- Outputs: none
- Required fields: none
- Optional fields: `level`
- Validation rules: `level` must be accepted by Python `logging.Logger.setLevel`
- Defaults: `logging.INFO`
- Status codes or result states: root logger has a JSON `StreamHandler` when it previously had no handlers; root logger level is set to `level`
- Error shapes: Python logging exceptions only; no custom errors
- Example input: `configure_logging()`
- Example output:
```json
{"timestamp":"2026-04-19T00:00:00+00:00","level":"INFO","logger":"example","message":"started"}
```

### Dockerfile `apps/forecast_service/Dockerfile`
- Name: `apps/forecast_service/Dockerfile`
- Type: container build/run contract
- Purpose: Build and run the forecast service independently from the future LLM service.
- Owner: forecast service
- Inputs: repository root build context containing `requirements.txt`, `apps`, and `shared`
- Outputs: container image running the forecast ASGI app
- Required fields: Docker build context must include `requirements.txt`, `apps`, and `shared`
- Optional fields: runtime `PORT`
- Validation rules: `PORT` must be accepted by Uvicorn as a port number
- Defaults: image sets `PORT=8000`; command uses `${PORT:-8000}`
- Status codes or result states: container starts Uvicorn for `apps.forecast_service.app.main:app`
- Error shapes: Docker or Uvicorn runtime errors
- Example input: `docker build -f apps/forecast_service/Dockerfile .`
- Example output: image with command `uvicorn apps.forecast_service.app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

### CLI Command `python3 -m pytest`
- Name: `python3 -m pytest`
- Type: CLI command
- Purpose: Run the forecast service foundation test suite.
- Owner: pytest configuration in `pyproject.toml`
- Inputs: project source tree and installed `requirements-dev.txt`
- Outputs: pytest result
- Required fields: Python environment with dev dependencies installed
- Optional fields: none
- Validation rules: tests under `tests` must pass
- Defaults: `testpaths = ["tests"]`; `pythonpath = ["."]`
- Status codes or result states: exit code `0` on pass; non-zero on failure
- Error shapes: pytest output
- Example input: `python3 -m pytest`
- Example output: `7 passed`

## 4. Data Contract

### Model `HealthResponse`
- Exact name: `HealthResponse`
- Fields: `status`
- Field types: `status: str`
- Required vs optional: `status` is required
- Allowed values: implementation returns `"ok"`; model does not enforce a literal enum
- Defaults: none on the model
- Validation constraints: Pydantic `BaseModel` string validation
- Migration notes: initial health response model
- Backward compatibility notes: `GET /health` contract depends on `status` being present and equal to `"ok"`

### Model `Settings`
- Exact name: `Settings`
- Fields: `supabase_url`, `supabase_service_key`, `port`
- Field types: `supabase_url: Optional[str]`, `supabase_service_key: Optional[str]`, `port: int`
- Required vs optional: all fields have defaults; no field is required at startup
- Allowed values: `port` accepts integers; Supabase fields accept strings or `None`
- Defaults: `supabase_url=None`, `supabase_service_key=None`, `port=8000`
- Validation constraints: Pydantic Settings validation; `.env` file is read when present; unknown extra settings are ignored
- Migration notes: initial shared config model
- Backward compatibility notes: Supabase fields are optional by design in this foundation

### Model `ForecastPlaceholder`
- Exact name: `ForecastPlaceholder`
- Fields: `ready`
- Field types: `ready: bool`
- Required vs optional: optional because default is provided
- Allowed values: boolean
- Defaults: `ready=False`
- Validation constraints: Pydantic `BaseModel` boolean validation
- Migration notes: provisional placeholder only
- Backward compatibility notes: NOT FINALIZED; do not treat this as a future forecast request or response DTO

### Class `ForecastService`
- Exact name: `ForecastService`
- Fields: none
- Field types: not applicable
- Required vs optional: not applicable
- Allowed values: not applicable
- Defaults: `ready()` returns `False`
- Validation constraints: none
- Migration notes: provisional placeholder only
- Backward compatibility notes: NOT FINALIZED; do not treat this as a real forecasting API

### JSON Shape `GET /health` Response
- Exact name: `GET /health` response
- Fields: `status`
- Field types: `status: string`
- Required vs optional: `status` is required
- Allowed values: `"ok"` is the only value returned by current implementation
- Defaults: always returns `"ok"`
- Validation constraints: response model is `HealthResponse`
- Migration notes: initial public health JSON shape
- Backward compatibility notes: keep this shape stable for health checks

## 5. Integration Contract
- Upstream dependencies: Python runtime; runtime dependencies from `requirements.txt`; test dependencies from `requirements-dev.txt` for verification.
- Downstream dependencies: NOT IMPLEMENTED. No downstream service calls are made.
- Services called: NOT IMPLEMENTED. The forecast service does not call Supabase, Spring Boot, Python LLM service, Grok, Resend, Stripe, or any external HTTP service.
- Endpoints hit: NOT IMPLEMENTED.
- Events consumed: NOT IMPLEMENTED.
- Events published: NOT IMPLEMENTED.
- Files read or written: `Settings` can read `.env` through Pydantic Settings when present; Docker build reads `requirements.txt`, `apps`, and `shared`; tests read source files for guardrail checks.
- Environment assumptions: the app can import and `GET /health` can run without `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
- Auth assumptions: NOT IMPLEMENTED. The forecast service has no auth validation in this foundation. Spring Boot remains responsible for auth and authorization before calling Python services in future work.
- Retry behavior: NOT IMPLEMENTED.
- Timeout behavior: NOT IMPLEMENTED.
- Fallback behavior: missing Supabase config falls back to `None`; missing `PORT` falls back to `8000`.
- Idempotency behavior: `GET /health` is read-only and has no side effects.

## 6. Usage Instructions for Other Engineers
- Use `apps.forecast_service.app.main:app` as the ASGI app import path.
- Use `GET /health` for forecast service health checks. Expect exactly `{"status": "ok"}` on success.
- Use `shared.config.settings.load_settings()` when tests or one-off code need fresh environment reads.
- Use `shared.config.settings.cached_settings()` for runtime code that should reuse one settings instance.
- Use `shared.logging.setup.configure_logging()` to initialize JSON logs.
- Use `apps/forecast_service/Dockerfile` to build the forecast service image independently from the future LLM service.
- Provide `PORT` only when the service should listen on a port other than `8000`.
- Do not require `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` for health checks or app import in this foundation.
- Handle loading states: NOT IMPLEMENTED; no async forecast operation exists.
- Handle empty states: NOT IMPLEMENTED; no forecast endpoint exists.
- Handle success states: only `GET /health` success is implemented.
- Handle failure states: custom API failure shapes are NOT IMPLEMENTED.
- Finalized: `GET /health`, `HealthResponse.status`, ASGI import path `apps.forecast_service.app.main:app`, optional Supabase config behavior, default `PORT=8000`, forecast service Dockerfile command shape.
- Provisional: `ForecastPlaceholder`, `ForecastService.ready()`, and `apps/forecast_service/app/api/forecasts.py`.
- MOCKED: no mocks are implemented.
- Stubbed: `ForecastPlaceholder` and `ForecastService.ready()` are placeholders and do not implement forecasting behavior.
- Must not be changed without coordination: forecast service must remain numeric-forecasting-only; frontend must not call Python services directly; Spring Boot remains the orchestrator and persistence owner; do not add chat, explanation, prompt, Grok, or purchase-order language code to `apps/forecast_service`.

## 7. Security and Authorization Notes
- Auth requirements: NOT IMPLEMENTED in the forecast service.
- Permission rules: NOT IMPLEMENTED in the forecast service.
- Tenancy rules: NOT IMPLEMENTED in the forecast service.
- Role checks: NOT IMPLEMENTED in the forecast service.
- Data isolation: enforced by future Spring Boot orchestration and Supabase RLS, not by this foundation.
- Sensitive fields: `patient_id` must not be added to forecast service payloads, logs, schemas, tests, prompts, exports, or generated outputs.
- Sanitization: NOT IMPLEMENTED in the forecast service. Spring Boot is expected to sanitize future payloads before calling Python services.
- Forbidden fields: `patient_id` is forbidden in this service boundary.
- Logging restrictions: do not log patient-level data, Supabase service keys, auth tokens, or future raw pharmacy uploads.
- Compliance concerns: service is prepared as a numeric forecasting boundary only; no LLM, prompt, chat, explanation, or purchase-order language behavior is present.
- Secret handling: `SUPABASE_SERVICE_KEY` is modeled in settings but not used; it must not be logged.

## 8. Environment and Configuration
- `SUPABASE_URL`: optional. Purpose is future Supabase project URL configuration. Missing value becomes `None`. Dev and prod behavior are currently the same because no Supabase client is implemented.
- `SUPABASE_SERVICE_KEY`: optional. Purpose is future Supabase service credential configuration if a later approved integration needs it. Missing value becomes `None`. It is sensitive and must not be logged. Dev and prod behavior are currently the same because no Supabase client is implemented.
- `PORT`: optional. Purpose is HTTP port for container/runtime command and app settings. Missing value defaults to `8000`. If provided, it must be parseable as an integer by Pydantic settings and usable by Uvicorn.
- `.env`: optional. Purpose is local environment loading through Pydantic Settings. Missing file is allowed.
- Docker `PYTHONDONTWRITEBYTECODE`: set to `1` in the Dockerfile.
- Docker `PYTHONUNBUFFERED`: set to `1` in the Dockerfile.

## 9. Testing and Verification
- Added `tests/forecast_service/test_health.py`: verifies `GET /health` returns HTTP `200` and JSON `{"status": "ok"}`.
- Added `tests/forecast_service/test_config.py`: verifies default `port=8000`, missing Supabase values become `None`, and env overrides are loaded.
- Added `tests/forecast_service/test_foundation_structure.py`: verifies `apps/forecast_service`, `apps/llm_service`, `shared/config`, `shared/logging`, and `shared/utils` exist; forecast service source excludes `grok`, `prompt`, `chat`, and `explanation`; dependencies exclude `prophet`; Dockerfile includes `apps.forecast_service.app.main:app` and `PORT:-8000`.
- Manual verification command run: `python3 -m pytest`.
- Final observed result: `7 passed`.
- Manual verification command run: `PYTHONPYCACHEPREFIX=/tmp/pharmacast-ai-pycache python3 -m compileall apps shared`.
- Final observed result: compileall succeeded.
- Dependency installation command used during verification: `python3 -m pip install -r requirements-dev.txt`.
- Known verification note: plain `python3 -m compileall apps shared` attempted to write bytecode under `/Users/adamsaleh/Library/Caches/com.apple.python/...` and was blocked by sandbox permissions; rerunning with `PYTHONPYCACHEPREFIX=/tmp/pharmacast-ai-pycache` succeeded.
- Known coverage gap: Docker image build was not run.
- Known coverage gap: no live Uvicorn server smoke test was run.
- Known coverage gap: no Supabase integration test exists because Supabase integration is NOT IMPLEMENTED.
- Known coverage gap: no real forecast endpoint test exists because real forecasting is NOT IMPLEMENTED.

## 10. Known Limitations and TODOs
- Real forecasting is NOT IMPLEMENTED.
- Prophet is NOT IMPLEMENTED and intentionally not installed.
- Forecast request DTO is NOT IMPLEMENTED.
- Forecast response DTO is NOT IMPLEMENTED.
- Forecast error shape is NOT IMPLEMENTED.
- Forecast generation endpoint is NOT IMPLEMENTED.
- Supabase client is NOT IMPLEMENTED.
- Database reads are NOT IMPLEMENTED.
- Database writes are NOT IMPLEMENTED.
- Spring Boot integration is NOT IMPLEMENTED.
- LLM service implementation is NOT IMPLEMENTED.
- Chat logic is NOT IMPLEMENTED.
- Explanation logic is NOT IMPLEMENTED.
- Prompt logic is NOT IMPLEMENTED.
- Grok client code is NOT IMPLEMENTED.
- Purchase-order drafting is NOT IMPLEMENTED.
- Auth and authorization are NOT IMPLEMENTED in Python.
- `ForecastPlaceholder` is provisional and should be replaced or removed when real forecast schemas are designed.
- `ForecastService.ready()` is provisional and should be replaced when real forecast behavior is implemented.
- `apps/forecast_service/app/api/forecasts.py` is a placeholder router and is not included in the app.
- `SUPABASE_SERVICE_KEY` is modeled but unused; future engineers should confirm whether the forecast service should ever access Supabase directly because Spring Boot currently owns reads/writes and orchestration.
- The project supports Python `>=3.9`, while the Dockerfile uses `python:3.12-slim`; this is compatible but should be revisited if production pins a different Python version.

## 11. Source of Truth Snapshot
- Final ASGI app: `apps.forecast_service.app.main:app`.
- Final public route: `GET /health`.
- Final health response: `{"status": "ok"}`.
- Final response model: `HealthResponse`.
- Final config model: `Settings`.
- Final config functions: `load_settings()`, `cached_settings()`.
- Final logging functions/classes: `configure_logging()`, `JsonFormatter`.
- Final provisional models/classes: `ForecastPlaceholder`, `ForecastService`.
- Final env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `PORT`.
- Final default port: `8000`.
- Final Dockerfile path: `apps/forecast_service/Dockerfile`.
- Final PRD path: `docs/prd/forecast-service-foundation.md`.
- Final plan path: `plans/forecast-service-foundation.md`.
- Final contract path: `docs/contracts/forecast-service-foundation.md`.
- Breaking changes from previous version: none; this is the initial Python forecast service foundation.

## 12. Copy-Paste Handoff for the Next Engineer
The Python forecast service foundation is implemented: shared mono-repo package boundaries, FastAPI app, `GET /health`, optional config for `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`, default `PORT=8000`, JSON logging setup, placeholder forecast modules, dedicated forecast Dockerfile, PRD, plan, tests, and this contract.

It is safe to depend on `apps.forecast_service.app.main:app`, `GET /health -> {"status": "ok"}`, `Settings`, `load_settings()`, `cached_settings()`, `configure_logging()`, and the forecast service Dockerfile command shape.

Remaining work: design and implement the real forecast request/response contract, add Prophet, enforce the 14-data-point minimum, implement numeric forecast generation, define structured forecast errors, connect Spring Boot to the service, and decide whether the forecast service should ever read from Supabase directly.

Traps: do not add chat, explanation, prompt, Grok, or purchase-order language code to `apps/forecast_service`; do not send or log `patient_id`; do not treat `ForecastPlaceholder` or `ForecastService.ready()` as finalized forecast interfaces; do not make health checks depend on Supabase credentials.

Read first: sections 3, 4, and 7 for the public route, data contracts, and security boundaries.
