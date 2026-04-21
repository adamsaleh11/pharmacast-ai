# Implementation Handoff Contract

## 1. Summary
- What is being fixed: the Python `forecast_service` must stop producing invalid forecast intervals for PharmaForecast and must return publishable forecast payloads that satisfy the backend contract.
- Why it is being fixed: the current weekly aggregation path can produce impossible `prophet_lower` / `prophet_upper` combinations for sparse or noisy demand, which then fail validation before persistence.
- What is in scope: the numeric forecasting path behind `POST /forecast/drug` and the per-DIN path inside `POST /forecast/batch`, including forecast aggregation, interval construction, and rejection of unsafe outputs.
- What is out of scope: Spring Boot persistence, frontend UI, Grok/LLM logic, chat, purchase-order drafting, auth, database migrations, and any unrelated model rewrite.
- Ownership: Python `forecast_service`, specifically the Prophet numeric forecasting implementation and its response assembly.

## 2. Files Added or Changed
- `docs/contracts/prophet-forecast-interval-fix.md` - created. Source-of-truth handoff for the interval fix.
- No Python source files are changed yet in this contract. The fix must be implemented in `apps/forecast_service`.

## 3. Public Interface Contract

### `POST /forecast/drug`
- Purpose: generate one numeric forecast for one DIN at one location.
- Inputs: `DrugForecastRequest`
- Required request fields:
  - `location_id`
  - `din`
  - `horizon_days`
  - `quantity_on_hand`
  - `lead_time_days`
  - `safety_multiplier`
  - `red_threshold_days` is optional and defaults to `3`
  - `amber_threshold_days` is optional and defaults to `7`
  - `supplemental_history` is optional
- Output on success: `ForecastResult`
- Success constraints:
  - `prophet_lower <= prophet_upper`
  - `prophet_lower >= 0`
  - `prophet_upper >= 0`
  - `predicted_quantity >= 0`
  - `days_of_supply >= 0`
  - `data_points_used >= 14`
- Failure behavior:
  - If the service cannot produce a publishable result, return a non-2xx response instead of a malformed success payload.

### `POST /forecast/batch`
- Purpose: stream per-DIN forecast results for multiple DINs.
- Inputs: `BatchForecastRequest`
- Output: SSE stream with one event per DIN and a final summary event.
- Success constraints:
  - Every per-DIN success payload must satisfy the same `ForecastResult` constraints as `POST /forecast/drug`
- Failure behavior:
  - If a DIN cannot be forecast safely, emit an error event for that DIN instead of a malformed success event.

### `POST /forecast/notification-check`
- Not changed by this fix.

## 4. Data Contract

### `ForecastRequest`
- Exact shape is unchanged.
- Field names must remain:
  - `location_id`
  - `din`
  - `horizon_days`
  - `quantity_on_hand`
  - `lead_time_days`
  - `safety_multiplier`
  - `supplemental_history`

### `ForecastResult`
- Exact shape is unchanged.
- Fields must remain:
  - `din`
  - `location_id`
  - `horizon_days`
  - `predicted_quantity`
  - `prophet_lower`
  - `prophet_upper`
  - `confidence`
  - `days_of_supply`
  - `avg_daily_demand`
  - `reorder_status`
  - `reorder_point`
  - `generated_at`
  - `data_points_used`

## 5. Integration Contract
- Upstream caller: Spring Boot `ForecastServiceClient`
- Downstream consumer: Spring Boot persistence logic
- Forecast data source: read-only Supabase `dispensing_records`
- Model source: Prophet only for numeric forecasting
- No patient identifiers may be logged, returned, or sent to any external API.
- Reorder status should use explicit day thresholds:
  - `RED` when `days_of_supply <= red_threshold_days`
  - `AMBER` when `days_of_supply <= amber_threshold_days`
  - `GREEN` otherwise

## 6. Required Algorithm
- Fit Prophet on the same granularity as the training data.
- Use complete time series rows for the model input instead of summing uncertainty bounds after the fact.
- Construct horizon totals from the forecast distribution, not by adding lower and upper bounds separately.
- Prefer sample-based aggregation for the horizon total:
  - forecast the horizon periods
  - collect `yhat` predictive samples
  - sum each sample path across the horizon
  - derive interval bounds from quantiles of the summed samples
- If the forecast distribution still cannot produce a valid interval, return a non-2xx result for the single-forecast path or an error event for batch.

## 7. Security and Compliance Notes
- `patient_id` must never leave the backend boundary.
- Only aggregated drug-level demand data may be sent to the forecasting service.
- No logs, prompts, or exported payloads may contain patient identifiers.

## 8. Testing and Verification
- Tests should verify:
  - a valid forecast payload always has ordered, non-negative intervals
  - bad intervals are rejected or transformed before success response
  - batch mode emits errors instead of malformed successes
  - the forecast service still returns existing operational metrics correctly
  - explicit reorder thresholds can be supplied without changing the response schema

## 9. Known Limitations and TODOs
- The exact root cause of the invalid interval is still a model/output-shaping problem.
- The implementation may still need a safe fallback path if Prophet predictive samples are unavailable or degenerate.
- Notification-check behavior is unchanged by this fix.

## 10. Copy-Paste Handoff for the Next Engineer
The backend already rejects invalid forecast payloads. The Python `forecast_service` now needs to produce publishable intervals directly from the forecast distribution, not from summed lower/upper bounds.

Use the existing `ForecastRequest` and `ForecastResult` shapes, keep `POST /forecast/drug` and `POST /forecast/batch`, and ensure every success payload satisfies `prophet_lower <= prophet_upper` with non-negative bounds.
