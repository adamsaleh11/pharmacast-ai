# Plan: Forecast Service Foundation

> Source PRD: `docs/prd/forecast-service-foundation.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: the only executable forecast service route in this slice is `GET /health`.
- **Health response**: `GET /health` returns exactly `{ "status": "ok" }`.
- **Python project**: the shared Python workspace uses a root `pyproject.toml`.
- **Service import path**: the forecast ASGI app is `apps.forecast_service.app.main:app`.
- **Service boundaries**: forecast service code is numeric-forecasting-only; no chat, explanation, prompt, Grok, or purchase-order language behavior.
- **Config**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `PORT` are modeled; Supabase values are optional for this foundation; `PORT` defaults to `8000`.
- **External services**: no external service calls, no database writes, and no Prophet dependency in this slice.
- **Deployment**: forecast service has its own Dockerfile and can be run independently from the future LLM service.

---

## Phase 1: Health Tracer Bullet

**User stories**: 1, 3, 10

### What to build

Create the minimum FastAPI forecast app and test harness that proves the service exposes its public health contract.

### Acceptance criteria

- [ ] `GET /health` returns HTTP 200.
- [ ] `GET /health` returns JSON exactly matching `{ "status": "ok" }`.
- [ ] The app can be imported through the forecast service ASGI path.

---

## Phase 2: Configuration and Logging Foundation

**User stories**: 4, 5, 6

### What to build

Add shared configuration and logging modules that the forecast app can use without requiring live Supabase credentials.

### Acceptance criteria

- [ ] Configuration exposes `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `PORT`.
- [ ] `PORT` defaults to `8000`.
- [ ] Missing Supabase values do not prevent app import or health checks.
- [ ] Environment overrides are observable through config loading.
- [ ] Logging can be initialized by the app without duplicate handlers.

---

## Phase 3: Service Structure and Separation Guardrails

**User stories**: 7, 8, 9, 12

### What to build

Add placeholder forecast API, schema, and service modules plus the requested shared mono-repo directories while enforcing the no-LLM/no-DB-write boundary.

### Acceptance criteria

- [ ] The repo contains separate `apps/forecast_service`, `apps/llm_service`, and `shared` package boundaries.
- [ ] Placeholder forecast router, schema, and service modules exist without implementing real forecasting.
- [ ] The forecast service has no chat, explanation, prompt, Grok, or LLM client behavior.
- [ ] The foundation does not include Prophet.
- [ ] The foundation does not implement database writes.

---

## Phase 4: Independent Forecast Deployment Shape

**User stories**: 2, 11

### What to build

Add the forecast-service-specific Dockerfile and project metadata needed to run the service independently.

### Acceptance criteria

- [ ] The forecast service has its own Dockerfile.
- [ ] The Dockerfile runs `apps.forecast_service.app.main:app`.
- [ ] The Dockerfile honors `PORT` with a default of `8000`.
- [ ] The root project metadata includes the runtime and test dependencies needed for this foundation.
- [ ] Local tests pass.
