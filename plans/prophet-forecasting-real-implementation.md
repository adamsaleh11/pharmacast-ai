# Plan: Prophet Forecasting - Real Implementation

> Source PRD: `docs/prd/prophet-forecasting-real-implementation.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `POST /forecast/drug`, `POST /forecast/batch`, `POST /forecast/notification-check`
- **Schema**: forecast requests take location-scoped DIN demand inputs; responses remain numeric and operational, with no patient-level data
- **Key models**: single-drug forecast result, batch SSE event, notification alert
- **Auth**: forecast service is treated as an internal boundary invoked by Spring Boot; no separate external auth flow is introduced in this feature
- **External services**: read-only Supabase access via `supabase-py`; Prophet for numeric forecasting; no writes to Supabase; no LLM/Grok usage
- **Operational stance**: conservative reorder bias, integer quantities only, end-to-end per-drug timeout, and no patient identifiers in logs or payloads

---

## Phase 1: Forecast Service Foundations

**User stories**: 19, 20, 21, 22, 23, 24

### What to build

Establish the runtime and service foundations needed for real forecasting without yet exposing the forecast behavior. This includes dependency wiring, Supabase client initialization strategy, shared request/response model scaffolding, and the minimal app wiring required for the new forecast routes to exist cleanly inside the current FastAPI service boundary.

### Acceptance criteria

- [ ] Forecast service dependencies include the libraries required for FastAPI, Supabase access, Prophet, data handling, and time/date handling
- [ ] The service can initialize a shared read-only Supabase client from settings without requiring live credentials at import time
- [ ] The forecast API surface exists under the expected route namespace and can be imported without side effects
- [ ] The existing health endpoint remains unchanged
- [ ] Tests verify the forecast-service boundary still excludes LLM/Grok behavior and preserves the service split

---

## Phase 2: Single-Drug Forecast Endpoint

**User stories**: 1, 2, 4, 5, 6, 7, 8, 15, 16, 17, 21, 22, 24, 25

### What to build

Implement `POST /forecast/drug` end to end for one location and one DIN. The endpoint reads dispensing history from Supabase, rejects insufficient history, aggregates demand into Monday-based weekly totals, optionally blends supplemental multi-location history, fits a Prophet model with Ontario holiday effects, and returns a numeric forecast with stock coverage and reorder guidance. This slice should include structured error handling for thin data and invalid inputs, and it should log forecast duration.

### Acceptance criteria

- [ ] A single forecast request returns predicted quantity, prediction interval bounds, confidence, days of supply, reorder point, reorder status, and generated timestamp
- [ ] The endpoint never calls Prophet when fewer than 14 usable rows are available
- [ ] Weekly aggregation is based on Monday week starts and sums demand correctly
- [ ] Supplemental history is merged additively by week when present
- [ ] Ontario statutory holidays influence the Prophet fit
- [ ] Quantities are returned as integers and timestamps are ISO-8601 UTC
- [ ] The endpoint returns a structured insufficient-data response instead of guessing
- [ ] Patient identifiers are not propagated into logs, outputs, or downstream payloads
- [ ] Forecast duration is recorded in logs without leaking sensitive row-level content

---

## Phase 3: Batch Streaming Forecasts

**User stories**: 10, 11, 12

### What to build

Implement `POST /forecast/batch` as a concurrent orchestration endpoint that runs individual drug forecasts in parallel and streams each completion over Server-Sent Events. The batch response should include per-drug success or error events as soon as they are available, then emit a final summary event with total, succeeded, and failed counts.

### Acceptance criteria

- [ ] Batch requests accept a list of DINs and location-level thresholds
- [ ] Per-drug forecasts run concurrently with a bounded worker pool
- [ ] Each completed drug produces an SSE event immediately rather than waiting for the whole batch
- [ ] Per-drug failures are returned inline and do not stop other drugs from completing
- [ ] The stream ends with a final summary event
- [ ] Batch processing respects the same per-drug timeout and compliance rules as the single-drug endpoint

---

## Phase 4: Notification Check Endpoint

**User stories**: 13, 14

### What to build

Implement `POST /forecast/notification-check` as the read-only scheduled-monitoring endpoint. It should enumerate distinct DINs for a location, run forecasts using default thresholds, and return only the items whose reorder status is amber or red. This endpoint must not persist anything and should be shaped for Spring Boot to store and route alerts downstream.

### Acceptance criteria

- [ ] The endpoint accepts a location identifier only
- [ ] The service queries distinct DINs from Supabase for that location
- [ ] Forecasts run with the default lead time and multiplier
- [ ] Only amber and red alerts are returned
- [ ] The service does not write to Supabase
- [ ] The response shape is stable and minimal for downstream persistence

---

## Phase 5: Hardening and Verification

**User stories**: 3, 9, 18, 19, 20, 24, 25

### What to build

Round out the feature with verification, logging, and failure-mode coverage. This phase should make the service safe to operate at scale by confirming timeout behavior, response contracts, and compliance boundaries under realistic and negative scenarios.

### Acceptance criteria

- [ ] Per-drug timeout enforcement covers the full workflow from read through response assembly
- [ ] Logging captures forecast timing and status without exposing sensitive identifiers or row content
- [ ] The forecast service remains read-only against Supabase
- [ ] Tests cover the public forecast contracts and the main error paths
- [ ] Tests verify integer-only quantities, ISO timestamp output, and the no-patient-id rule
- [ ] Tests verify the health endpoint and existing scaffold behavior remain intact

