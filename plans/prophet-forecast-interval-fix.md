# Plan: Prophet Forecast Interval Fix

> Source PRD: `docs/contracts/prophet-forecast-interval-fix.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `POST /forecast/drug`, `POST /forecast/batch`
- **Schema**: keep `ForecastRequest` and `ForecastResult` field names unchanged
- **Key models**: Prophet-based numeric forecast output, per-DIN SSE stream, publishability validation
- **Auth**: internal service boundary invoked by Spring Boot; no new auth flow
- **External services**: Prophet only for numeric forecasting; no LLM/Grok usage
- **Safety rule**: a success payload must never contain invalid interval bounds

---

## Phase 1: Contracted Failure and Validation

**User stories**: return only publishable single-forecast payloads, reject malformed interval output, preserve batch error isolation

### What to build

Lock the public behavior around invalid forecast output. Add regression coverage that drives the service through its real HTTP interface and batch stream so bad intervals are rejected or emitted as errors instead of success payloads.

### Acceptance criteria

- [ ] `POST /forecast/drug` returns a non-2xx response for an invalid interval forecast
- [ ] `POST /forecast/batch` emits an error event for an invalid interval forecast
- [ ] Existing successful forecast responses remain unchanged

---

## Phase 2: Distribution-Based Horizon Aggregation

**User stories**: produce valid forecast intervals for realistic demand series, avoid impossible summed bounds

### What to build

Replace the horizon-total interval construction with sample-based aggregation from the forecast distribution. Use Prophet outputs in a way that produces ordered, non-negative bounds even when the history is sparse or noisy.

### Acceptance criteria

- [ ] Horizon totals are derived from forecast samples instead of summing lower and upper bounds independently
- [ ] Final intervals are always ordered and non-negative on success paths
- [ ] The service still returns the same response fields and route shapes

---

## Phase 3: Safe Fallbacks and Hardening

**User stories**: never return malformed success payloads, keep batch resilient under edge cases

### What to build

Add fallback handling for degenerate forecast distributions and verify the service remains stable across the real production-like inputs already used by Spring.

### Acceptance criteria

- [ ] If the forecast distribution cannot produce a valid interval, the service fails safely instead of returning malformed success data
- [ ] Batch processing continues for other DINs when one DIN fails
- [ ] Test coverage includes the main success and failure paths for the new algorithm

