# Backend Forecast Tightening Contract

## 1. Purpose

This contract tells the Spring/backend engineer what must be true at the backend boundary so the Python forecast service produces sensible numbers and the UI does not display stale, inflated, or internally inconsistent results.

If anything still looks wrong after the Python fixes, the backend should verify the request payload, the deployed service version, and the data shaping done before calling the Python service.

## 2. What Is Fixed in Python Already

- The forecast service now normalizes history to weekly totals before fitting Prophet.
- The forecast service now derives horizon intervals from the forecast distribution instead of stitching invalid lower/upper bounds together.
- The forecast service now calculates stock coverage from request `quantity_on_hand` and forecasted demand.
- The forecast service now uses explicit reorder thresholds from the request.
- The forecast service returns a response header identifying the patched code path:
  - `X-Forecast-Code-Path: weekly-normalized-samples-v2`

## 3. Request Contract

### `POST /forecast/drug`

The backend must send:

- `location_id`: UUID string
- `din`: 8-digit DIN string
- `horizon_days`: one of `7`, `14`, or `30`
- `quantity_on_hand`: current on-hand stock for that DIN at that location
- `lead_time_days`: non-negative integer, default `2`
- `safety_multiplier`: one of `1.5`, `1.0`, or `0.75`
- `red_threshold_days`: integer, default `3`
- `amber_threshold_days`: integer, default `7`
- `supplemental_history`: optional weekly history array

### `supplemental_history`

If provided, each item must be a weekly aggregate object:

- `week`: week anchor string, ideally Monday-based
- `quantity`: non-negative integer

Do not include `patient_id` anywhere in the payload.

## 4. Output Contract

The backend should expect this `ForecastResult` shape on success:

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

Success payload constraints:

- `prophet_lower <= prophet_upper`
- `prophet_lower >= 0`
- `prophet_upper >= 0`
- `predicted_quantity >= 0`
- `days_of_supply >= 0`
- `data_points_used >= 14`

## 5. Reorder Logic

Reorder status is now threshold-based and must be interpreted with these fields:

- `RED` if `days_of_supply <= red_threshold_days`
- `AMBER` if `days_of_supply <= amber_threshold_days`
- `GREEN` otherwise

The backend should not re-derive status from lead time alone if it is already sending explicit thresholds.

## 6. Expected Magnitude

The service is tuned for weekly dispensing history.

For a 14-day forecast, the backend should expect the predicted quantity to be in the same order of magnitude as roughly two weeks of weekly demand, not seven times higher than the weekly demand rate.

If a DIN is dispensing about:

- `350 units/week`, the 14-day forecast should usually be around `700 units`
- `140 units/week`, the 14-day forecast should usually be around `280 units`
- `55 units/week`, the 14-day forecast should usually be around `110 units`

If results are still inflated by about 7x, the backend should check:

- that it is talking to the patched service build
- that it is not caching an old response
- that the request payload is not being transformed into row-level daily records before the call

## 7. Deployment Verification

The backend should verify the forecast response header:

- `X-Forecast-Code-Path: weekly-normalized-samples-v2`

If the header is missing, the service instance is not the patched build.

## 8. What The Backend Should Tighten If Anything Is Wrong

1. Confirm the deployed forecast service is the patched build.
2. Confirm the backend sends `quantity_on_hand` from the request body or inventory snapshot, not from historical dispense rows.
3. Confirm `red_threshold_days` and `amber_threshold_days` are populated with business defaults or per-location values.
4. Confirm the backend is not passing patient-level records or raw CSV rows directly to the forecast service.
5. Confirm the frontend is not displaying stale cached results.
6. Confirm any local diagnostics are reading the current JSON response body, not an older UI state.

## 9. Notes for the Backend Engineer

- The Python service is expected to be idempotent for identical inputs.
- The Python service should fail safely instead of returning malformed success payloads.
- If the backend still sees inflated demand after this contract is followed, the issue is most likely a stale deployment or a request-shaping bug upstream of Python.

