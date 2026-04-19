# PharmaForecast

**PharmaForecast** is an AI-powered drug demand forecasting SaaS for independent pharmacies in Ottawa, Canada.

## Primary Goal

Help independent pharmacies:

- upload dispensing history
- forecast drug demand
- identify reorder risks
- understand inventory trends
- receive proactive alerts
- generate purchase orders

---

## System Architecture

### Frontend

- Next.js (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Query

### Core Backend

- Java Spring Boot 3+
- Java 21
- Spring Security
- Spring Data JPA
- Flyway
- PostgreSQL

### Database / Auth / Realtime

- Supabase
  - PostgreSQL
  - Auth
  - Realtime
  - RLS

### Forecasting Pipeline

- Python FastAPI
- Prophet

### LLM Pipeline

- Python FastAPI
- Grok Cloud lightweight model

### Email

- Resend

### Billing

- Stripe

### Hosting

- Vercel for Next.js
- Fly.io Toronto region (`yyz`) for Spring Boot
- Fly.io Toronto region (`yyz`) for Python forecast service
- Fly.io Toronto region (`yyz`) for Python LLM service
- Supabase Canada region for PostgreSQL/Auth

---

## Critical Architecture Rules

- Spring Boot is the orchestration and enforcement layer.
- Spring Boot owns:
  - auth validation
  - organization/location authorization
  - business logic
  - DB reads/writes
  - persistence
  - notifications
  - billing
  - all calls to Python services
  - sanitization before any LLM request
- Forecast service owns numeric forecasting only.
- LLM service owns language generation only.
- Forecast service never generates explanations or chat responses.
- LLM service never generates forecast numbers.
- Frontend never calls Python services directly.
- Frontend only talks to Spring Boot APIs and Supabase Auth/session state.

---

## Compliance Rules

- All data should remain in Canada where possible.
- `patient_id` may exist in database but must never be sent to Grok or any external LLM.
- `patient_id` must never appear in logs, prompts, exports, chat context, or generated purchase orders.
- Only aggregated drug-level data may be sent to the LLM service.
- The product supports inventory decisions, not medical or prescribing decisions.
- Supabase RLS must isolate tenant data.
- Organization/location ownership must always be validated server-side, even if RLS exists.

---

## Core Domain Model

- organizations
- locations
- users
- drugs
- dispensing_records
- forecasts
- drug_thresholds
- stock_adjustments
- purchase_orders
- notifications
- csv_uploads
- chat_messages
- notification_settings

---

## Product Rules

- CSV upload is the only ingestion method for v1.
- Forecasts are generated on demand when the pharmacist clicks **Generate**.
- Notification jobs may run forecast checks silently in the background.
- Grok is only used for:
  1. written forecast explanations
  2. chat assistant responses
  3. purchase order drafting
- Prophet is the only forecasting engine in v1.
- Multi-location is supported.
- Network-level demand can be used only as aggregated supplemental signal.
- Savings calculations must be evidence-based and never fabricated.
- UTC for persisted timestamps.
- ET for user-facing scheduling and notification timing.
- UUIDs for all primary keys.

---

## Default Business Settings

- Default `lead_time_days = 2`
- Default `red_threshold_days = 3`
- Default `amber_threshold_days = 7`

### Safety Multiplier Mapping

- `conservative = 1.5`
- `balanced = 1.0`
- `aggressive = 0.75`

---

## Forecast Rules

- Prophet must never run on fewer than 14 data points.
- Forecast horizons: 7, 14, 30 days.
- Quantities must be integers.
- Days of supply rounded to 1 decimal place.
- Forecast confidence derived from prediction interval width.
- Forecast service must return structured errors.
- Spring Boot persists forecasts, not Python.

---

## LLM Rules

- LLM service receives only sanitized, structured payloads from Spring Boot.
- LLM service must validate payload schema.
- LLM prompts must never include patient-level fields.
- LLM outputs should be concise, professional, and pharmacy-friendly.
- Temperature should be low and deterministic.
- LLM service should support explanation, chat, and purchase-order drafting separately.
- LLM caching can exist at the Spring Boot layer and/or LLM layer where appropriate.

---

## Design Direction

- clinical
- trustworthy
- modern
- fast
- readable under pressure
- deep navy primary
- teal accent
- crisp white surfaces
- compact but clear data density

---

## Engineering Rules

- Build production-quality folder structures.
- Prefer explicit DTOs and schemas.
- Prefer clean integration contracts between agents.
- If an upstream dependency is not yet built, write integration-ready code with TODO markers, mocks, or clear interfaces.
- Do not invent incompatible API shapes.
- Respect ownership boundaries between services.
