## Problem Statement

Independent pharmacies in Ottawa need a forecasting service that turns dispensing history into actionable demand and reorder guidance. Today the forecast service scaffold exists, but it does not produce real forecasts, so the product cannot surface predicted quantities, stock coverage, reorder risk, or batch operational alerts.

This matters now because pharmacy ordering is time-sensitive: false negatives create stockouts and lost trust, while overly aggressive ordering ties up cash and shelf space. The first release must therefore be accurate enough to support reorder decisions, fast enough to use interactively, and conservative enough to avoid understating risk.

## Solution

Build a real Prophet-based forecasting boundary inside the Python forecast service. The service will read dispensing history from Supabase, aggregate history to weekly demand, optionally blend supplemental multi-location history, fit a Prophet model with Ontario holiday effects, and return numeric forecasts with stock-of-supply and reorder guidance.

The service will expose three endpoints:

- a single-drug forecast endpoint for interactive forecast generation
- a batch forecast endpoint that streams results as each DIN completes
- a notification-check endpoint that returns only amber/red reorder alerts for scheduled monitoring

The solution should optimize for pharmacy profitability and trust by being conservative on stockout risk, easy to explain operationally, and strict about compliance boundaries. It must never write to Supabase, never include patient identifiers, and never introduce LLM logic into the forecast service.

## User Stories

1. As a pharmacy owner, I want to generate a forecast for one drug at one location, so that I can decide whether to reorder it now.
2. As a pharmacy manager, I want the forecast to use my location’s dispensing history first, so that the prediction reflects local demand patterns.
3. As a pharmacy manager, I want supplemental multi-location history to influence the forecast when available, so that shared demand signals improve visibility for newer or thinner-history locations.
4. As a pharmacist, I want the forecast to fail cleanly when there is not enough history, so that I do not act on unsupported predictions.
5. As a pharmacy owner, I want the forecast output to include predicted quantity, confidence, days of supply, and reorder status, so that I can make a fast purchasing decision.
6. As a pharmacy manager, I want reorder status to be conservative, so that the model prioritizes avoiding stockouts over minimizing inventory.
7. As a pharmacy owner, I want the service to respect Ontario holiday effects, so that demand spikes and drops around statutory holidays are modeled more realistically.
8. As a pharmacist, I want weekly aggregation to be stable and predictable, so that forecasts align with operational reporting and reorder cadence.
9. As a pharmacy owner, I want the forecast to complete quickly enough for interactive use, so that I can run it during order review without waiting on a long process.
10. As an operations user, I want batch forecasts for many DINs, so that I can refresh a location’s forecast set in one request.
11. As an operations user, I want batch results to stream as they finish, so that I can see progress before the slowest drug completes.
12. As an operations user, I want batch processing to continue even if one DIN fails, so that a single bad forecast does not block the rest.
13. As a scheduler, I want a notification-check endpoint that returns only amber and red alerts, so that daily monitoring stays focused on actionable reorder risk.
14. As a backend scheduler, I want notification-check results to be read-only, so that Spring Boot can persist alerts and handle downstream orchestration itself.
15. As a pharmacy owner, I want confidence to reflect the uncertainty of the forecast, so that I can judge whether the model is strong enough to rely on.
16. As a pharmacist, I want low-history forecasts to be treated cautiously, so that sparse data does not look stronger than it is.
17. As a compliance officer, I want patient identifiers excluded from all forecasting behavior, so that no regulated personal data leaves the dispensing system boundary.
18. As a compliance officer, I want the forecast service to avoid writing to the database, so that persistence remains centralized in Spring Boot and easier to audit.
19. As a technical operator, I want the service to use a shared Supabase client per process, so that reads are efficient and thread-safe enough for batch execution.
20. As a technical operator, I want each drug forecast to have a 30-second end-to-end timeout, so that the service does not stall under bad inputs or slow upstream reads.
21. As a pharmacy owner, I want quantities to remain integers, so that the output matches how inventory is ordered and counted.
22. As a pharmacy manager, I want the service to return ISO-8601 timestamps, so that downstream systems can parse outputs reliably.
23. As a backend integrator, I want the response schemas to be stable and explicit, so that Spring Boot can persist or relay results without guessing.
24. As an operator, I want forecast duration logged, so that slowdowns can be detected before they affect users.
25. As a pharmacy owner planning for Ontario expansion, I want the design to work beyond Ottawa, so that the model can scale across the province without changing core behavior.

## Implementation Decisions

- Build the real forecasting logic inside the Python forecast service boundary rather than in Spring Boot.
- Keep the service focused on numeric forecasting only; explanation text, chat, and purchase-order language remain outside this service.
- Add a dedicated single-drug forecast endpoint for interactive use.
- Add a batch forecast endpoint that processes multiple DINs concurrently and streams completion events via Server-Sent Events.
- Add a notification-check endpoint for scheduled daily monitoring.
- Read dispensing history from Supabase using the service key and the existing shared settings model.
- Use one shared, lazily initialized Supabase client per process to avoid recreating clients on every request.
- Treat the full per-drug workflow as the timeout boundary, not only the Prophet fit step.
- Enforce a hard minimum of 14 dispensing rows before any Prophet call is made.
- Aggregate history to weekly totals using Monday week starts.
- Merge supplemental history additively by week when provided, while keeping primary location history dominant.
- Fit Prophet with yearly seasonality, weekly seasonality, and a conservative changepoint prior.
- Generate Ontario statutory holidays for the data range plus two future years.
- Return only numeric forecast fields and operational stock guidance.
- Keep all quantity values as integers in responses.
- Derive days of supply from the last 30 days of actual demand.
- Derive reorder point from average daily demand, lead time, and safety multiplier.
- Keep reorder-status thresholds conservative and deterministic.
- Stream batch forecast results incrementally, not only after all forecasts finish.
- Return per-drug errors in batch mode without stopping the entire batch.
- Return only amber and red items from notification-check.
- Do not write forecast outputs to Supabase; Spring Boot owns persistence.
- Do not include patient identifiers in request handling, logs, outputs, or any downstream payloads.
- Keep the forecast service free of any LLM/Grok implementation.

## Testing Decisions

- Test the single-drug endpoint as an external contract, not by reaching into internal helper functions.
- Test the insufficient-data path to ensure the service never calls Prophet below the minimum row threshold.
- Test weekly aggregation behavior with representative daily records spanning multiple weeks.
- Test supplemental history merging to verify additive behavior by week.
- Test Ontario holiday generation behavior against known holiday dates.
- Test batch streaming behavior by consuming SSE output and verifying per-drug completion events plus final summary.
- Test per-drug timeout handling as a user-visible failure path.
- Test notification-check filtering to ensure only amber and red items are returned.
- Test that quantities remain integers and timestamps serialize in ISO-8601 format.
- Test that patient identifiers are not emitted into outputs or logs.
- Use the existing forecast-service foundation tests as prior art for contract-focused health/config/boundary checks.
- Add service-level tests for forecast outputs and error cases rather than implementation-detail tests for Prophet internals.

## Out of Scope

- Forecast explanations, chat, and purchase-order text generation.
- Any LLM or Grok integration.
- Any write path to Supabase from the forecast service.
- Frontend UI changes.
- Spring Boot orchestration, persistence, and alert storage.
- Payment, billing, and subscription logic.
- Any rework of the existing health endpoint or foundation scaffolding.
- Any expansion of patient-level data handling beyond the existing compliance boundary.

## Further Notes

- This feature is intentionally conservative: the model should prefer avoiding stockouts over minimizing inventory.
- The service should remain usable for Ottawa first, but the design should not hard-code Ottawa-specific behavior beyond Ontario holiday handling and Canada-only data assumptions.
- If forecast quality is weak because of thin or noisy history, the service should surface that uncertainty rather than smooth it away.
- Batch behavior should tolerate partial failures, because operators need useful results even when one DIN is malformed or under-supported.
- The forecast service should stay as a clean numeric boundary so that future explanation text can be added in the LLM service without contaminating forecasting logic.
- The next planning step should turn this PRD into tracer-bullet implementation slices covering dependencies, API schemas, Supabase reads, Prophet integration, SSE streaming, and verification.
