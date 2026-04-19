## Problem Statement

PharmaForecast needs a dedicated Python forecasting service foundation before Spring Boot can safely orchestrate demand forecast generation. The backend and frontend foundations already establish the ownership boundary: Spring Boot owns authentication, authorization, persistence, business logic, and all calls to Python services; the forecast service owns numeric forecasting only. Today there is no Python service scaffold in this workspace, so future forecast work would lack a deployable app boundary, shared configuration pattern, logging convention, test harness, and Docker entrypoint.

This matters now because upcoming forecast features depend on a clean separation from the LLM service. The forecast service must be independently deployable, health-checkable, and ready for future Prophet-backed numeric endpoints without introducing chat, explanation, prompt, Grok, or database write behavior.

## Solution

Create the shared Python mono-repo foundation with separate application boundaries for `forecast_service` and `llm_service`, shared utility packages, a root Python project definition, and an independently deployable FastAPI forecast service. The forecast app will expose `GET /health` returning `{ "status": "ok" }`, load service configuration from environment variables, initialize structured logging, and provide placeholder router/schema/service modules for future numeric forecast endpoints.

The foundation will not implement real forecasting logic, database writes, LLM calls, chat behavior, prompt construction, or Grok client code. It will be lean enough to run locally and in Docker without live Supabase credentials, while still modeling the environment variables future integration code expects.

## User Stories

1. As a backend engineer, I want a dedicated forecast service app, so that Spring Boot can later call a clear numeric forecasting boundary.
2. As a platform engineer, I want the forecast service to be independently deployable, so that it can run separately from the future LLM service.
3. As a developer, I want a health endpoint, so that local development, Docker, and Fly.io health checks can verify the service is running.
4. As a developer, I want configuration centralized through environment variables, so that runtime settings are predictable across local and deployed environments.
5. As a developer, I want missing Supabase credentials not to break health checks, so that the foundation can run before real Supabase integration exists.
6. As a developer, I want a shared logging module, so that future services can use consistent log formatting.
7. As a Python forecast engineer, I want placeholder forecast API, schema, and service modules, so that future numeric forecast work has an obvious home.
8. As a compliance reviewer, I want the forecast service to contain no prompt, chat, explanation, Grok, or purchase-order language code, so that service responsibilities remain separated.
9. As a backend engineer, I want the foundation to avoid database writes, so that Spring Boot remains the persistence owner.
10. As a developer, I want tests that exercise public behavior, so that refactors do not break the service contract.
11. As a deployment engineer, I want a forecast-service-specific Dockerfile, so that the service can be built and run without coupling to the future LLM service.
12. As a future forecast implementer, I want Prophet deferred until real forecasting is added, so that foundation work avoids unverified heavy dependencies.

## Implementation Decisions

- The Python repo will use a root `pyproject.toml` as the project and dependency source of truth.
- The app package will follow the requested mono-repo structure and use `apps.forecast_service.app` as the importable FastAPI package.
- The forecast ASGI app will be importable as `apps.forecast_service.app.main:app`.
- The forecast service will expose `GET /health`.
- The health response will be exactly `{ "status": "ok" }`.
- The service will model `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `PORT` in config.
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` will be optional during this foundation. Code that later depends on them must validate them at point of use.
- `PORT` will default to `8000`.
- Logging will use JSON-formatted standard library logging by default to suit deployed service logs.
- No `/api/v1/forecast` execution endpoint will be added yet. A placeholder API router package may exist, but it must not advertise a working forecast contract.
- Error response contracts for forecast generation are deferred until a real forecast endpoint exists.
- The `llm_service` path will be present only as a separate boundary placeholder. It will not contain forecast code or LLM implementation logic in this feature.
- Prophet will not be installed in this foundation. It will be added with the first real forecasting slice.
- Tests will cover public behavior and guardrails: health endpoint behavior, config defaults/optional Supabase env behavior, and separation from forbidden LLM/chat/prompt/Grok terms in forecast service code.

## Testing Decisions

- Tests should verify behavior through public interfaces and stable contracts, not implementation details.
- The tracer bullet test will exercise `GET /health` through FastAPI's test client.
- Config tests should verify observable settings behavior: default `PORT`, optional Supabase values, and env override behavior.
- Separation tests should verify the forecast service source does not contain forbidden LLM ownership terms such as Grok client logic, prompt logic, chat logic, or explanation logic.
- Docker should be validated at least structurally through the presence of a forecast-service-specific Dockerfile with an ASGI command for the forecast app. Full image build can be deferred if dependency installation is blocked by network access.

## Out of Scope

- Real Prophet forecasting.
- Forecast request/response API contracts.
- Forecast generation endpoint behavior.
- Database reads or writes.
- Supabase client implementation.
- Spring Boot integration.
- LLM service implementation.
- Chat assistant behavior.
- Forecast explanations.
- Prompt construction.
- Grok client code.
- Purchase-order drafting.
- Fly.io deployment configuration.
- Authentication or authorization inside Python services.

## Further Notes

- Spring Boot remains the enforcement and orchestration layer and will eventually call the forecast service.
- Spring Boot persists forecasts; Python does not.
- The frontend must never call the forecast service directly.
- Any future payloads must exclude `patient_id`.
- Future forecast logic must enforce the domain rule that Prophet never runs on fewer than 14 data points.
- Future forecast outputs must align with backend enum/status contracts: confidence `low`, `medium`, `high`; reorder status `ok`, `amber`, `red`; horizons `7`, `14`, `30`.
