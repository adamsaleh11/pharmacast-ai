# PharmaForecast

PRODUCT: PharmaForecast — an AI-powered drug demand forecasting SaaS for independent pharmacies in Ottawa, Canada.

STACK:
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS, Shadcn/ui, React Query, Supabase JS client
- Backend: Java 21, Spring Boot 3+, Spring Security, Spring Data JPA, Flyway, Supabase (PostgreSQL + Realtime + Auth + RLS)
- Background Jobs: Spring @Scheduled + @Async with a ThreadPoolTaskExecutor (no external queue in v1)
- Email: Resend (via HTTP client, not SMTP)
- AI Pipeline: Python FastAPI — two separate services:
    - forecast_service: Facebook Prophet only (numeric forecasting)
    - llm_service: xAI Grok API only (explanations, chat, purchase order text)
- Hosting: Fly.io Toronto (yyz) for Spring Boot + both Python services, Vercel for Next.js, Supabase ca-central-1 for DB
- Billing: Stripe

COMPLIANCE:
- All data must stay in Canada (PHIPA + PIPEDA)
- patient_id must NEVER be sent to Grok, any LLM, or any external API
- patient_id must never appear in logs, prompts, exports, or generated documents
- Only aggregated drug-level data (DIN, quantities, dates) is sent to the LLM service
- Supabase RLS enforces data isolation per tenant
- Spring Boot validates organization/location ownership server-side on every request — never rely on RLS alone

CORE DATA MODEL:
- organizations (id, name, stripe_customer_id, subscription_status, trial_ends_at, created_at, updated_at)
- locations (id, organization_id, name, address, deactivated_at, created_at, updated_at)
- users (id, organization_id, email, role: 'owner', created_at, updated_at)
- drugs (id, din, name, strength, form, therapeutic_class, manufacturer, status, last_refreshed_at, created_at, updated_at)
- dispensing_records (id, location_id, din, dispensed_date, quantity_dispensed, quantity_on_hand, cost_per_unit nullable, patient_id nullable)
- forecasts (id, location_id, din, generated_at, forecast_horizon_days, predicted_quantity, confidence: 'HIGH'|'MEDIUM'|'LOW', days_of_supply, reorder_status: 'GREEN'|'AMBER'|'RED', prophet_lower, prophet_upper, avg_daily_demand, reorder_point, data_points_used)
- drug_thresholds (id, location_id, din, lead_time_days, red_threshold_days, amber_threshold_days, safety_multiplier: 'CONSERVATIVE'|'BALANCED'|'AGGRESSIVE', notifications_enabled)
- stock_adjustments (id, location_id, din, adjustment_quantity, adjusted_at, note)
- purchase_orders (id, location_id, generated_at, grok_output text, line_items jsonb, status: 'DRAFT'|'SENT')
- notifications (id, organization_id, location_id nullable, type, payload jsonb, sent_at nullable, read_at nullable)
- csv_uploads (id, location_id, filename, status: 'PENDING'|'PROCESSING'|'SUCCESS'|'ERROR', error_message text nullable, row_count nullable, drug_count nullable, validation_summary jsonb nullable, uploaded_at)
- chat_messages (id, location_id, role: 'user'|'assistant', content, created_at, updated_at)
- notification_settings (id, organization_id unique, daily_digest_enabled, weekly_insights_enabled, critical_alerts_enabled, created_at, updated_at)

FEATURES ALREADY DECIDED:
- CSV upload is the only data ingestion method for v1
- Prophet runs ON DEMAND when Generate is clicked (plus silent background notification check via @Scheduled)
- LLM only fires when: Explain clicked, Chat message sent, Purchase order generated
- Multi-location: patient data isolated per location, aggregated demand signals shareable across locations
- Savings calculation: variance-based (recommended qty vs actual qty × cost_per_unit)
- Health Canada DIN API enriches drug metadata on CSV upload, refreshed weekly via @Scheduled

DEFAULT BUSINESS SETTINGS:
- Default lead_time_days = 2
- Default red_threshold_days = 3
- Default amber_threshold_days = 7
- Safety multiplier: CONSERVATIVE = 1.5, BALANCED = 1.0, AGGRESSIVE = 0.75

SPRING BOOT CONVENTIONS (apply everywhere):
- Package root: com.pharmaforecast
- All controllers annotated @RestController + @RequestMapping
- All services annotated @Service + @Transactional where appropriate
- All repositories extend JpaRepository<Entity, UUID>
- DTOs use Java records (or @Data Lombok classes) — never expose JPA entities directly
- Validation via @Valid + Jakarta Bean Validation annotations
- Global exception handler via @RestControllerAdvice
- Auth context via custom principal injected by Spring Security filter
- Configuration in application.yml with spring.profiles.active = local | prod
- All IDs are UUIDs
- All timestamps are UTC OffsetDateTime in DB, serialized as ISO-8601 strings in JSON
- Flyway migrations in src/main/resources/db/migration/V{n}__{description}.sql

## SPECIAL RECALLS

- The Python forecast service foundation now lives in this repo under `apps/forecast_service`.
- The forecast ASGI import path is `apps.forecast_service.app.main:app`.
- The forecast service currently exposes only `GET /health`, returning exactly `{"status": "ok"}`.
- Forecast service config is in `shared/config/settings.py` and models `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `PORT`.
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are intentionally optional for the foundation; `/health` and app import must not require live Supabase credentials.
- `PORT` defaults to `8000`.
- The forecast service Dockerfile is `apps/forecast_service/Dockerfile` and runs `uvicorn apps.forecast_service.app.main:app`.
- Prophet is intentionally not installed yet; add it only when real forecasting behavior is implemented.
- `apps/forecast_service/app/api/forecasts.py`, `ForecastPlaceholder`, and `ForecastService.ready()` are placeholders, not finalized forecast contracts.
- The `apps/llm_service` package exists only as a boundary placeholder; no LLM behavior is implemented there yet.
- Keep all chat, explanation, prompt, Grok, and purchase-order language logic out of `apps/forecast_service`.
- Contract handoff for the forecast foundation is `docs/contracts/forecast-service-foundation.md`; read it before extending the Python service.
- Local verification for the forecast foundation is `python3 -m pytest`; the latest observed result was 7 passing tests.
