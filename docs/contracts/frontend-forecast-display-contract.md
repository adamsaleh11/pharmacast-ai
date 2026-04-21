# Frontend Forecast Display Contract

## 1. Purpose

This contract tells the frontend engineer how to render forecast results so the UI stays consistent with the backend forecast service and does not re-derive business logic incorrectly.

If the UI still looks wrong after the backend and Python fixes, the frontend should verify it is rendering the latest response body and not a cached or stale forecast state.

## 2. What the Frontend Must Trust

The frontend must treat these backend fields as source of truth:

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

Do not recalculate:

- forecasted demand
- days of supply
- reorder status
- reorder point

Render the backend values directly.

## 3. Expected Forecast Meaning

The forecast is a 14-day or 7-day numeric demand projection depending on the selected horizon.

The UI should display:

- `predicted_quantity` as the forecasted demand for the selected horizon
- `days_of_supply` as the stock coverage from the backend
- `reorder_status` as the backend decision label

The frontend must not treat `quantity_on_hand` as a forecast input. It is a stock coverage input only.

## 4. Required UI Behavior

### Forecast row

Each drug row should display:

- DIN and drug name
- current stock
- days of supply
- forecasted demand with the selected horizon label
- confidence
- status
- last generated timestamp

### Status rendering

The UI should render:

- `RED` as a critical reorder state
- `AMBER` as a cautionary reorder state
- `GREEN` as an acceptable state

Do not map these statuses to custom labels unless they are semantically identical.

### Forecast freshness

The UI should:

- update the displayed row with the latest response after a Generate click
- avoid showing old forecast numbers after a newer response arrives
- use the `generated_at` value to show recency

## 5. Response Validation Expectations

The frontend should only render a forecast row as successful if the response contains:

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

If the response is an error response, show an error state instead of partially rendering stale numbers.

## 6. Staleness and Caching Rules

The frontend should not reuse a prior forecast response after a new Generate action.

If the backend response includes:

- `X-Forecast-Code-Path: weekly-normalized-samples-v2`

the UI may use that as a diagnostic indicator that the patched backend build is active, but it should not depend on that header for normal rendering.

## 7. Expected Magnitude

For weekly dispensing history, the UI should expect a 14-day forecast to be approximately two weeks of weekly demand, not seven times the weekly number.

If the UI is still showing numbers like:

- `2859` for a drug averaging about `350/week`
- `1321` for a drug averaging about `140/week`
- `612` for a drug averaging about `56/week`
- `3` or `0` for drugs with steady weekly demand

then the UI is probably rendering stale or incorrect data and should not consider the forecast reliable.

## 8. User-Facing Presentation Notes

- Keep the selected horizon visible near the forecasted demand number.
- Show `days_of_supply` with one decimal place.
- Show `predicted_quantity` as a whole number if the backend returns a whole number.
- Do not infer stock status from forecasted demand alone.
- Use the backend status label as the displayed status.

## 9. Error Handling

If the forecast response is non-2xx or has an error payload:

- show a clear error message
- do not keep the previous forecast row visible as if it were current
- do not silently fall back to cached data without telling the user

## 10. Frontend Verification

The frontend should verify:

1. The newest response body is the one being rendered.
2. The displayed forecast magnitude is reasonable relative to the CSV weekly history.
3. The row updates after Generate and does not preserve stale values from a prior call.
4. The UI is not re-deriving days of supply or reorder status locally.

