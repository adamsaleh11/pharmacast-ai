# Implementation Handoff Contract

## 1. Summary

- Implemented a standalone FastAPI LLM service boundary for PharmaForecast in `apps/llm_service`.
- The service exposes `POST /llm/explain`, `POST /llm/chat`, and `POST /llm/purchase-order`.
- It calls Groq Cloud only and does not contain forecasting, Prophet, Supabase, or persistence logic.
- It was implemented so Spring Boot can delegate all pharmacist-facing language generation to a separate Python service.
- In scope: service scaffold, shared Groq client, recursive patient-data validator, endpoint wiring, exception mapping, SSE chat streaming, local Groq env setup, and contract tests.
- Out of scope: forecasting, database access, Spring Boot code, frontend code, retries/fallbacks, live Groq smoke tests, Dockerfile for `llm_service`, and any persistence for chat or purchase-order drafts.
- This implementation is owned by `apps/llm_service` with shared helpers in `shared/`.

## 2. Files Added or Changed

- `.env` - updated locally and gitignored; added `GROQ_API_KEY` and `GROQ_MODEL` entries for copy-paste use, without committing the secret value.
- `pyproject.toml` - updated; added `httpx` and `pydantic` to the repository dependency list so the LLM service can run and be tested.
- `shared/logging/setup.py` - updated; JSON logging now preserves structured `extra` fields such as Groq feature name, token estimate, and duration.
- `shared/validators.py` - created; recursive payload validator that blocks patient-related fields before any LLM call.
- `shared/grok_client.py` - created; async Groq client wrapper with completion, streaming, concurrency limiting, logging, and error translation.
- `apps/llm_service/__init__.py` - updated; marks the standalone LLM service package.
- `apps/llm_service/app/__init__.py` - created; marks the FastAPI app package.
- `apps/llm_service/app/main.py` - created; FastAPI entrypoint, app-level exception handlers, and router inclusion.
- `apps/llm_service/app/api/__init__.py` - created; registers the `/llm` route group.
- `apps/llm_service/app/api/explain.py` - created; implements `POST /llm/explain`.
- `apps/llm_service/app/api/chat.py` - created; implements `POST /llm/chat` as SSE streaming.
- `apps/llm_service/app/api/purchase_order.py` - created; implements `POST /llm/purchase-order`.
- `apps/llm_service/app/schemas/common.py` - created; shared Pydantic base model with `extra="allow"`.
- `apps/llm_service/app/schemas/explain.py` - created; explanation request/response DTOs.
- `apps/llm_service/app/schemas/chat.py` - created; chat request DTO.
- `apps/llm_service/app/schemas/purchase_order.py` - created; purchase-order request/response DTOs.
- `apps/llm_service/app/schemas/__init__.py` - created; schema package marker.
- `apps/llm_service/app/services/__init__.py` - created; service package marker.
- `apps/llm_service/requirements.txt` - created; service-local dependency manifest for FastAPI, httpx, pydantic, and Uvicorn.
- `tests/llm_service/test_explain_endpoint.py` - created; contract tests for explanation behavior and payload rejection.
- `tests/llm_service/test_chat_endpoint.py` - created; contract tests for SSE chat streaming and payload rejection.
- `tests/llm_service/test_purchase_order_endpoint.py` - created; contract tests for purchase-order generation and payload rejection.
- `tests/llm_service/test_grok_client.py` - created; contract tests for Groq completion, streaming, and upstream error handling.
- `docs/prd/llm-service-real-implementation.md` - created; feature PRD that defined the behavior and boundaries.
- `plans/llm-service-real-implementation.md` - created; tracer-bullet implementation plan used to sequence the work.
- `docs/contracts/llm-service-real-implementation.md` - created; this handoff contract.

## 3. Public Interface Contract

### `apps.llm_service.app.main:app`

- Name: `apps.llm_service.app.main:app`
- Type: FastAPI ASGI application
- Purpose: runtime entrypoint for the LLM service
- Owner: `apps/llm_service/app/main.py`
- Inputs: inbound HTTP requests
- Outputs: JSON responses, SSE responses, and FastAPI error responses
- Required fields: none at app startup
- Optional fields: environment variables described in section 8
- Validation rules: route-level Pydantic validation plus app-level payload safety checks
- Defaults: app title is `PharmaForecast LLM Service`
- Status codes or result states: serves `/llm/explain`, `/llm/chat`, and `/llm/purchase-order`
- Error shapes: `LLM_UNAVAILABLE` and `INVALID_PAYLOAD` are handled explicitly; other validation errors use FastAPI defaults
- Example input: `uvicorn apps.llm_service.app.main:app --host 0.0.0.0 --port 8000`
- Example output: a running FastAPI app exposing the LLM routes

### `POST /llm/explain`

- Name: `POST /llm/explain`
- Type: HTTP endpoint
- Purpose: generate a pharmacist-facing explanation of the reorder recommendation
- Owner: `apps.llm_service.app.api.explain`
- Inputs: `ExplainRequest`
- Outputs: `ExplainResponse`
- Required fields: `location_id`, `din`, `drug_name`, `strength`, `therapeutic_class`, `quantity_on_hand`, `days_of_supply`, `avg_daily_demand`, `horizon_days`, `predicted_quantity`, `prophet_lower`, `prophet_upper`, `confidence`, `reorder_status`, `reorder_point`, `lead_time_days`, `data_points_used`, `weekly_quantities`
- Optional fields: none
- Validation rules: `quantity_on_hand` must be `>= 0`; `validate_no_patient_data(request.model_dump())` runs before prompt construction or Groq access; `ExplainRequest` inherits `extra="allow"` from `AllowExtraModel`
- Defaults: none
- Status codes or result states: `200` on success, `400` for forbidden patient-data fields, `503` if Groq is unavailable, `422` for FastAPI/Pydantic validation errors
- Error shapes:
  - `{"error":"INVALID_PAYLOAD","message":"Patient data is not permitted in LLM requests"}`
  - `{"error":"LLM_UNAVAILABLE","message":"Try again in a moment"}`
- Provider failure behavior: any `shared.grok_client.GrokApiException` raised by Groq Cloud is mapped to `503 LLM_UNAVAILABLE`; the service does not expose provider payloads or upstream status codes to callers.
- `generated_at`: always returned on success; format is ISO-8601 UTC with offset, e.g. `2026-04-21T12:34:56.789012+00:00`.
- `max_tokens`: always supplied server-side as `600`; callers do not infer or pass this value. The upstream Groq request uses `max_completion_tokens`.
- Empty response behavior: the endpoint returns `{"explanation": "" ...}` if Groq returns an empty assistant message; it does not return `null`.
- Example input:
```json
{
  "location_id": "11111111-1111-1111-1111-111111111111",
  "din": "12345678",
  "drug_name": "Amoxicillin",
  "strength": "500 mg",
  "therapeutic_class": "Antibiotic",
  "quantity_on_hand": 15,
  "days_of_supply": 4.5,
  "avg_daily_demand": 3.2,
  "horizon_days": 14,
  "predicted_quantity": 45,
  "prophet_lower": 40,
  "prophet_upper": 51,
  "confidence": "HIGH",
  "reorder_status": "RED",
  "reorder_point": 12.0,
  "lead_time_days": 2,
  "data_points_used": 28,
  "weekly_quantities": [4, 5, 6, 7, 8, 9, 10, 11]
}
```
- Example output:
```json
{
  "explanation": "The drug is trending upward, so reorder now.",
  "generated_at": "2026-04-21T00:00:00+00:00"
}
```

### `POST /llm/chat`

- Name: `POST /llm/chat`
- Type: HTTP endpoint with streaming response
- Purpose: stream chat output token by token
- Owner: `apps.llm_service.app.api.chat`
- Inputs: `ChatRequest`
- Outputs: `text/event-stream`
- Required fields: `system_prompt`, `messages`
- Optional fields: none
- Validation rules: `validate_no_patient_data({"messages": request.messages, "system": request.system_prompt})` runs before streaming begins; `ChatRequest` inherits `extra="allow"` from `AllowExtraModel`; each message is passed through as a plain dict
- Defaults: none
- Status codes or result states: `200` on success, `400` for forbidden patient-data fields, `503` if Groq is unavailable, `422` for FastAPI/Pydantic validation errors
- Error shapes:
  - `{"error":"INVALID_PAYLOAD","message":"Patient data is not permitted in LLM requests"}`
  - `{"error":"LLM_UNAVAILABLE","message":"Try again in a moment"}`
- Provider failure behavior: any `shared.grok_client.GrokApiException` raised during streaming is mapped to `503 LLM_UNAVAILABLE`; partial SSE output may already have been sent before the failure is observed.
- SSE behavior: yes, this is a true `text/event-stream` response.
- SSE event shape:
  - token event: `data: {"token":"<token>"}\n\n`
  - final event: `data: {"done":true,"total_tokens":<estimate>}\n\n`
- `max_tokens`: always supplied server-side as `2000`; callers do not infer or pass this value. The upstream Groq request uses `max_completion_tokens`.
- `generated_at`: not present on this endpoint.
- Example input:
```json
{
  "system_prompt": "You are a helpful assistant.",
  "messages": [
    { "role": "user", "content": "Say hello" }
  ]
}
```
- Example output:
```text
data: {"token":"Hel"}

data: {"token":"lo"}

data: {"done":true,"total_tokens":1}
```

### `POST /llm/purchase-order`

- Name: `POST /llm/purchase-order`
- Type: HTTP endpoint
- Purpose: draft purchase-order text for pharmacist review
- Owner: `apps.llm_service.app.api.purchase_order`
- Inputs: `PurchaseOrderRequest`
- Outputs: `PurchaseOrderResponse`
- Required fields: `pharmacy_name`, `location_address`, `today`, `horizon_days`, `drugs`
- Optional fields: none
- Validation rules: `validate_no_patient_data(request.model_dump())` runs before prompt construction or Groq access; `current_stock` must be `>= 0`; `PurchaseOrderRequest` and `PurchaseOrderDrug` inherit `extra="allow"` from `AllowExtraModel`
- Defaults: none
- Status codes or result states: `200` on success, `400` for forbidden patient-data fields, `503` if Groq is unavailable, `422` for FastAPI/Pydantic validation errors
- Error shapes:
  - `{"error":"INVALID_PAYLOAD","message":"Patient data is not permitted in LLM requests"}`
  - `{"error":"LLM_UNAVAILABLE","message":"Try again in a moment"}`
- Provider failure behavior: any `shared.grok_client.GrokApiException` raised by Groq Cloud is mapped to `503 LLM_UNAVAILABLE`; the service does not expose provider payloads or upstream status codes to callers.
- `generated_at`: always returned on success; format is ISO-8601 UTC with offset, e.g. `2026-04-21T12:34:56.789012+00:00`.
- `max_tokens`: always supplied server-side as `1500`; callers do not infer or pass this value. The upstream Groq request uses `max_completion_tokens`.
- Empty response behavior: the endpoint returns `{"order_text": "" ...}` if Groq returns an empty assistant message; it does not return `null`.
- Example input:
```json
{
  "pharmacy_name": "Downtown Pharmacy",
  "location_address": "123 Bank St, Ottawa, ON",
  "today": "2026-04-21",
  "horizon_days": 14,
  "drugs": [
    {
      "drug_name": "Amoxicillin",
      "strength": "500 mg",
      "din": "12345678",
      "current_stock": 8,
      "predicted_quantity": 40,
      "days_of_supply": 2.5,
      "reorder_status": "RED",
      "avg_daily_demand": 3.1,
      "lead_time_days": 2
    }
  ]
}
```
- Example output:
```json
{
  "order_text": "Order Amoxicillin 500 mg and keep a two-week buffer.",
  "generated_at": "2026-04-21T00:00:00+00:00"
}
```

### `shared.grok_client.call_grok`

- Name: `shared.grok_client.call_grok`
- Type: async function
- Purpose: send a non-streaming chat completion request to Groq Cloud and return the assistant text
- Owner: `shared/grok_client.py`
- Inputs: `messages: list[dict]`, `max_tokens: int`
- Outputs: `str`
- Required fields: `messages`, `max_tokens`
- Optional fields: none
- Validation rules: uses `GROQ_API_KEY` with legacy fallback to `GROK_API_KEY`; model comes from `GROQ_MODEL` with legacy fallback to `GROK_MODEL`, defaulting to `openai/gpt-oss-120b`; temperature is fixed at `0.6`; `top_p` is fixed at `0.95`; `reasoning_effort` is fixed at `medium`; `include_reasoning` is fixed at `false`; request body uses `/chat/completions` with `stream: false` and `max_completion_tokens`
- Defaults: `GROQ_MODEL` defaults to `openai/gpt-oss-120b`; timeout is `60.0` seconds
- Status codes or result states: returns the content string on success
- Error shapes: raises `GrokApiException(status_code, message)` on HTTP or transport failure
- Example input:
```python
await call_grok([{"role": "user", "content": "Hello"}], max_tokens=600)
```
- Example output:
```python
"generated text"
```

### `shared.grok_client.stream_grok`

- Name: `shared.grok_client.stream_grok`
- Type: async generator function
- Purpose: stream token chunks from Groq Cloud as they arrive
- Owner: `shared/grok_client.py`
- Inputs: `messages: list[dict]`, `max_tokens: int`
- Outputs: `AsyncGenerator[str, None]`
- Required fields: `messages`, `max_tokens`
- Optional fields: none
- Validation rules: uses `GROQ_API_KEY` with legacy fallback to `GROK_API_KEY`; model comes from `GROQ_MODEL` with legacy fallback to `GROK_MODEL`, defaulting to `openai/gpt-oss-120b`; temperature is fixed at `0.6`; `top_p` is fixed at `0.95`; `reasoning_effort` is fixed at `medium`; `include_reasoning` is fixed at `false`; request body uses `/chat/completions` with `stream: true` and `max_completion_tokens`
- Defaults: `GROQ_MODEL` defaults to `openai/gpt-oss-120b`; timeout is `120.0` seconds
- Status codes or result states: yields only non-empty token strings; stops when Groq Cloud emits `[DONE]`
- Error shapes: raises `GrokApiException(status_code, message)` on HTTP or transport failure
- Example input:
```python
async for token in stream_grok([{"role": "user", "content": "Hello"}], max_tokens=2000):
    ...
```
- Example output:
```python
"Hel"
"lo"
```

### `shared.grok_client.feature_context`

- Name: `shared.grok_client.feature_context`
- Type: context manager
- Purpose: tag Groq call logs with the feature name that triggered the request
- Owner: `shared/grok_client.py`
- Inputs: `feature: str`
- Outputs: context manager scope with no return value
- Required fields: `feature`
- Optional fields: none
- Validation rules: none
- Defaults: none
- Status codes or result states: the active feature name is read from a context variable by Groq calls
- Error shapes: none
- Example input:
```python
with feature_context("explain"):
    ...
```
- Example output: logs emitted by Groq calls include `feature="explain"`

### `shared.validators.validate_no_patient_data`

- Name: `shared.validators.validate_no_patient_data`
- Type: function
- Purpose: recursively reject payloads that contain patient-related or prescriber-related fields
- Owner: `shared/validators.py`
- Inputs: `payload: dict`
- Outputs: none
- Required fields: a dictionary payload
- Optional fields: none
- Validation rules: recursively walks nested dictionaries and lists; rejects any key in `FORBIDDEN_FIELDS`
- Defaults: none
- Status codes or result states: returns `None` when safe; raises `ValueError` when forbidden fields are found
- Error shapes: `ValueError("Patient data field '<field>' found in LLM payload — this is not permitted")`
- Example input:
```python
validate_no_patient_data({"messages": [{"patient_id": "abc123"}]})
```
- Example output: raises `ValueError`

### Request acceptance and extra-field behavior

- `ExplainRequest`, `ChatRequest`, `PurchaseOrderRequest`, and `PurchaseOrderDrug` all inherit from `AllowExtraModel`, so extra keys are accepted by the Pydantic schema layer.
- Extra keys are ignored by prompt construction unless they are explicitly read by the endpoint code.
- The service still rejects forbidden keys recursively even when they appear only in extra fields.
- `quantity_on_hand` is required for `ExplainRequest` and must be present in the Spring payload.
- `weekly_quantities` can be any list length; the service does not enforce exactly eight items.
- `lead_time_days` is required in `ExplainRequest`; Python does not default it.
- `confidence` and `reorder_status` are free-form strings in the schema; Python does not enforce enums.
- The recursive forbidden-field denylist is exactly: `patient_id`, `patient_name`, `patient_dob`, `prescriber_id`, and `prescriber_name`.

### Startup and import behavior

- `shared.grok_client` and `apps.llm_service.app.main:app` can be imported without `GROQ_API_KEY` present.
- The service only fails when an endpoint actually attempts a Groq call.
- Missing `GROQ_API_KEY` during a request raises `GrokApiException(503, "GROQ_API_KEY is not configured")`, which is then translated by the app into `503 {"error":"LLM_UNAVAILABLE","message":"Try again in a moment"}`.

## 4. Data Contract

### `AllowExtraModel`

- Exact name: `AllowExtraModel`
- Fields: none
- Field types: not applicable
- Required vs optional: not applicable
- Allowed values: not applicable
- Defaults: Pydantic `extra="allow"`
- Validation constraints: extra keys are accepted by the schema layer
- Migration notes: this is a shared base model used by the LLM request and response DTOs
- Backward compatibility notes: request DTOs currently tolerate extra keys at the schema layer and rely on `validate_no_patient_data` for the patient-data policy

### `ExplainRequest`

- Exact name: `ExplainRequest`
- Fields:
  - `location_id: str`
  - `din: str`
  - `drug_name: str`
  - `strength: str`
  - `therapeutic_class: str`
  - `quantity_on_hand: int`
  - `days_of_supply: float`
  - `avg_daily_demand: float`
  - `horizon_days: int`
  - `predicted_quantity: int`
  - `prophet_lower: int`
  - `prophet_upper: int`
  - `confidence: str`
  - `reorder_status: str`
  - `reorder_point: float`
  - `lead_time_days: int`
  - `data_points_used: int`
  - `weekly_quantities: list[int]`
- Field types: strings, integers, floats, and integer lists as listed above
- Required vs optional: all fields are required
- Allowed values: `confidence` and `reorder_status` are free-form strings in the schema; the service does not enforce enums
- Defaults: none
- Validation constraints: `quantity_on_hand` must be `>= 0`; extra keys are allowed at the schema layer
- Migration notes: first finalized explanation request DTO
- Backward compatibility notes: `weekly_quantities` is expected to contain the last eight weeks in oldest-first order, but the schema does not enforce length

### `ExplainResponse`

- Exact name: `ExplainResponse`
- Fields:
  - `explanation: str`
  - `generated_at: str`
- Field types: strings
- Required vs optional: both fields are required
- Allowed values: `generated_at` is an ISO-8601 UTC timestamp string
- Defaults: none
- Validation constraints: response is serialized by FastAPI/Pydantic
- Migration notes: first finalized explanation response DTO
- Backward compatibility notes: keep both fields stable for Spring Boot consumers

### `ChatRequest`

- Exact name: `ChatRequest`
- Fields:
  - `system_prompt: str`
  - `messages: list[dict[str, str]]`
- Field types: string and list of string-to-string dictionaries
- Required vs optional: both fields are required
- Allowed values: `messages` is used with `role` values such as `user` and `assistant`, but the schema does not enforce an enum
- Defaults: none
- Validation constraints: extra keys are allowed at the schema layer; `validate_no_patient_data` is the enforcement gate
- Migration notes: first finalized chat request DTO
- Backward compatibility notes: the streaming endpoint is stateless and expects the caller to resend full history when needed

### `PurchaseOrderDrug`

- Exact name: `PurchaseOrderDrug`
- Fields:
  - `drug_name: str`
  - `strength: str`
  - `din: str`
  - `current_stock: int`
  - `predicted_quantity: int`
  - `days_of_supply: float`
  - `reorder_status: str`
  - `avg_daily_demand: float`
  - `lead_time_days: int`
- Field types: strings, integers, and floats as listed above
- Required vs optional: all fields are required
- Allowed values: `reorder_status` is a free-form string in the schema; the service does not enforce an enum
- Defaults: none
- Validation constraints: `current_stock` must be `>= 0`; extra keys are allowed at the schema layer
- Migration notes: first finalized purchase-order line-item DTO
- Backward compatibility notes: one request can contain multiple drugs

### `PurchaseOrderRequest`

- Exact name: `PurchaseOrderRequest`
- Fields:
  - `pharmacy_name: str`
  - `location_address: str`
  - `today: str`
  - `horizon_days: int`
  - `drugs: list[PurchaseOrderDrug]`
- Field types: strings, integer, and nested DTO list
- Required vs optional: all fields are required
- Allowed values: `today` is treated as a caller-supplied date string; the schema does not enforce a format
- Defaults: none
- Validation constraints: extra keys are allowed at the schema layer; `validate_no_patient_data` is the enforcement gate
- Migration notes: first finalized purchase-order request DTO
- Backward compatibility notes: Spring Boot must continue to provide all pharmacist and inventory context

### `PurchaseOrderResponse`

- Exact name: `PurchaseOrderResponse`
- Fields:
  - `order_text: str`
  - `generated_at: str`
- Field types: strings
- Required vs optional: both fields are required
- Allowed values: `generated_at` is an ISO-8601 UTC timestamp string
- Defaults: none
- Validation constraints: response is serialized by FastAPI/Pydantic
- Migration notes: first finalized purchase-order response DTO
- Backward compatibility notes: keep both fields stable for Spring Boot consumers

### `FORBIDDEN_FIELDS`

- Exact name: `FORBIDDEN_FIELDS`
- Fields:
  - `patient_id`
  - `patient_name`
  - `patient_dob`
  - `prescriber_id`
  - `prescriber_name`
- Field types: string set members
- Required vs optional: not applicable
- Allowed values: exact keys only
- Defaults: none
- Validation constraints: any occurrence of these keys anywhere in a nested dict/list payload must raise `ValueError`
- Migration notes: this is the service-level compliance denylist
- Backward compatibility notes: changes to this set must be coordinated because they affect compliance behavior

### SSE event payloads from `POST /llm/chat`

- Exact name: `chat SSE payloads`
- Fields:
  - token event: `token: str`
  - done event: `done: bool`
  - done event: `total_tokens: int`
- Field types: JSON object values
- Required vs optional: token events carry `token`; the final event carries `done` and `total_tokens`
- Allowed values: `done` is always `true` in the final event
- Defaults: `total_tokens` is estimated from emitted text, not provider usage metadata
- Validation constraints: emitted as `data: <json>\n\n`
- Migration notes: first finalized streaming payload shape
- Backward compatibility notes: keep the token event shape and final done event stable

## 5. Integration Contract

- Upstream dependencies: Groq Cloud OpenAI-compatible API at `https://api.groq.com/openai/v1/chat/completions`.
- Downstream dependencies: Spring Boot is the caller and remains the owner of auth, tenancy, and data assembly.
- Services called: Groq Cloud only.
- Endpoints hit: `POST /chat/completions` with `stream: false` for normal completions and `stream: true` for chat streaming.
- Events consumed: none.
- Events published: chat SSE events are published to the HTTP caller, not to an internal queue.
- Files read or written: no database files, no Supabase reads, and no persistent output files are written by the service; the local `.env` file is used for runtime configuration only.
- Environment assumptions: the app can import and start without `GROQ_API_KEY`; endpoint calls require `GROQ_API_KEY` to be present. Legacy `GROK_API_KEY` / `GROK_MODEL` are accepted as compatibility fallbacks in code.
- Auth assumptions: no end-user auth is implemented in Python; Spring Boot must authenticate and authorize before calling this service.
- Retry behavior: no retry logic is implemented.
- Timeout behavior: `call_grok` uses a 60 second HTTP timeout; `stream_grok` uses a 120 second HTTP timeout.
- Fallback behavior: no fallback model, backup provider, or circuit breaker is implemented.
- Idempotency behavior: requests are read-only language generation calls; repeated requests may produce different text.

## 6. Usage Instructions for Other Engineers

- What they can rely on: the route names, response envelopes, patient-data rejection behavior, and Groq error mapping are finalized for this slice.
- What they should call/import/use: import `app` from `apps.llm_service.app.main` for serving; use `shared.grok_client.call_grok`, `shared.grok_client.stream_grok`, `shared.grok_client.feature_context`, and `shared.validators.validate_no_patient_data` for new LLM work.
- What inputs they must provide: Spring Boot must send complete aggregated context for explanations and purchase orders, plus the system prompt and history for chat; do not omit the fields required by the DTOs.
- What outputs they will receive: `ExplainResponse` and `PurchaseOrderResponse` return generated text plus `generated_at`; `POST /llm/chat` returns an SSE stream with `token` events and a final `done` event.
- What loading, empty, success, and failure states to handle: empty Groq output is currently allowed as an empty string; validation errors return `400 INVALID_PAYLOAD`; Groq failures return `503 LLM_UNAVAILABLE`; schema errors return FastAPI `422`.
- What is finalized: route paths, error envelopes, the forbidden field denylist, the use of a single Groq model, and the streaming event shape.
- What is still provisional: prompt wording, local `.env` values, and any future Docker packaging for the service.
- What is mocked or stubbed: all tests mock the Groq HTTP client; no live Groq integration test is present yet.
- What must not be changed without coordination: route names, error envelope strings, the recursive patient-data validator, the forbidden field list, and the structured logging keys emitted by Groq calls.

## 7. Security and Authorization Notes

- No auth or role checks are implemented in the Python service; Spring Boot owns authorization and tenant isolation.
- The service must never send `patient_id`, `patient_name`, `patient_dob`, `prescriber_id`, or `prescriber_name` to Groq.
- The recursive validator runs before every endpoint calls Groq.
- Logs are intended to contain only structured metadata such as feature name, estimated input tokens, and duration; payload content is not intentionally logged.
- The service consumes only aggregated drug-level operational context from Spring Boot.
- No Supabase access exists in this service, which keeps the LLM boundary separate from persistence and tenant data reads.

## 8. Environment and Configuration

- `GROQ_API_KEY` - required secret for Groq Cloud calls; if missing, `shared.grok_client` raises `GrokApiException(503, "GROQ_API_KEY is not configured")` when a request is made. Legacy `GROK_API_KEY` is accepted as a fallback.
- `GROQ_MODEL` - optional model selector; the code defaults to `openai/gpt-oss-120b`, and the local `.env` in this workspace currently overrides it to the same value. Legacy `GROK_MODEL` is accepted as a fallback.
- `.env` - local, gitignored file that holds the runtime values used during development.
- `PORT` - still supported by `shared.config.settings.Settings`, but it is not consumed by the LLM service code path directly.
- `SUPABASE_URL` - still supported by `shared.config.settings.Settings`, but unused by the LLM service.
- `SUPABASE_SERVICE_KEY` - still supported by `shared.config.settings.Settings`, but unused by the LLM service.
- Fixed runtime settings in code:
  - temperature: `0.6`
  - top_p: `0.95`
  - reasoning_effort: `medium`
  - include_reasoning: `false`
  - concurrency cap: `10`
  - standard Groq timeout: `60.0` seconds
  - streaming Groq timeout: `120.0` seconds

## 9. Testing and Verification

- Tests added or updated:
  - `tests/llm_service/test_explain_endpoint.py`
  - `tests/llm_service/test_chat_endpoint.py`
  - `tests/llm_service/test_purchase_order_endpoint.py`
  - `tests/llm_service/test_grok_client.py`
- What was manually verified: the full test suite passed after the implementation was added, including the new LLM service tests and the existing forecast-service tests.
- How to run the tests: `python3 -m pytest`
- How to locally validate the feature: run `python3 -m pytest tests/llm_service` for the LLM slice, or `python3 -m pytest` for the full workspace.
- Known gaps in test coverage: no live Groq smoke test, no Docker build test for `llm_service`, and no load/performance test for the 10-call concurrency cap.

## 10. Known Limitations and TODOs

- `apps/llm_service/Dockerfile` does not exist yet.
- There is no live Groq integration test; all Groq behavior is mocked in tests.
- No retry, fallback model, or circuit breaker behavior exists.
- `GROQ_MODEL` code default is `openai/gpt-oss-120b`, and the workspace `.env` matches that value.
- The SSE `total_tokens` value is an estimate derived from emitted text, not provider-reported usage.
- Request DTOs allow extra keys at the schema layer, so the recursive validator is the actual policy enforcement mechanism.
- Chat message shape is permissive; `role` values are not enum-enforced in the DTO.

## 11. Source of Truth Snapshot

- Final route names: `POST /llm/explain`, `POST /llm/chat`, `POST /llm/purchase-order`
- Final DTO/model names: `ExplainRequest`, `ExplainResponse`, `ChatRequest`, `PurchaseOrderDrug`, `PurchaseOrderRequest`, `PurchaseOrderResponse`, `AllowExtraModel`
- Final helper names: `validate_no_patient_data`, `FORBIDDEN_FIELDS`, `call_grok`, `stream_grok`, `feature_context`, `GrokApiException`
- Final status values: `LLM_UNAVAILABLE`, `INVALID_PAYLOAD`
- Final SSE event names: token event with `{"token": "<token>"}`, final event with `{"done": true, "total_tokens": <estimate>}`
- Final key file paths: `apps/llm_service/app/main.py`, `shared/grok_client.py`, `shared/validators.py`, `tests/llm_service/test_explain_endpoint.py`, `tests/llm_service/test_chat_endpoint.py`, `tests/llm_service/test_purchase_order_endpoint.py`, `tests/llm_service/test_grok_client.py`
- Breaking changes from previous version: the provider switched from xAI Grok to Groq Cloud, and the service now uses `GROQ_API_KEY` / `GROQ_MODEL` with legacy fallbacks for compatibility.

## 12. Copy-Paste Handoff for the Next Engineer

Already done: the LLM service scaffold, Groq client, recursive safety validator, three public endpoints, error mapping, SSE streaming, and contract tests are in place.

Safe to depend on: the `/llm/*` route names, the `INVALID_PAYLOAD` and `LLM_UNAVAILABLE` error envelopes, the SSE token/done stream shape, and the forbidden-field denylist.

Still to build: a `apps/llm_service/Dockerfile`, any live Groq smoke test, and any future prompt refinement or retry strategy.

