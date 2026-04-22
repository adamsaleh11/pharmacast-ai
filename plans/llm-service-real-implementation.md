# Plan: LLM Service Real Implementation

> Source PRD: [docs/prd/llm-service-real-implementation.md](/Users/adamsaleh/Downloads/pharmacast-ai/docs/prd/llm-service-real-implementation.md)

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `POST /llm/explain`, `POST /llm/chat`, and `POST /llm/purchase-order`.
- **Schema**: request and response bodies are validated at the FastAPI boundary with Pydantic models; generated timestamps are ISO-8601 strings.
- **Key models**: one Groq Cloud model for all endpoints, configured by `GROQ_MODEL` and defaulting to `openai/gpt-oss-120b`.
- **Auth**: no end-user auth inside Python; Spring Boot owns auth, tenant isolation, and payload assembly before calling the service.
- **External services**: the service calls Groq Cloud only; it reads no data from Supabase and contains no forecasting logic.
- **Safety boundary**: every endpoint validates payloads recursively to reject patient-related fields before any Grok call is made.
- **Concurrency**: Grok calls are globally limited with a process-wide concurrency cap.
- **Streaming**: chat responses are returned as Server-Sent Events with token events followed by a final done event.

---

## Phase 1: Service Scaffold and Boundaries

**User stories**: 8, 11, 12, 18

### What to build

Create the standalone LLM service package boundary, add the service-specific dependency surface, and wire the app entrypoint and shared runtime conventions needed for future endpoint work. This slice should make the service discoverable as its own FastAPI app without pulling in forecasting code or Supabase access.

### Acceptance criteria

- [ ] The repository contains a distinct `llm_service` FastAPI app boundary separate from the forecast service.
- [ ] The LLM service can start with shared configuration and logging conventions already in place.
- [ ] The service has no forecasting imports, Prophet usage, or Supabase reads.
- [ ] The service dependency set includes the packages required for FastAPI, HTTP client access, validation, and serving.

---

## Phase 2: Grok Client and Safety Guard

**User stories**: 9, 10, 13, 14, 15, 17

### What to build

Implement the shared Groq client and the recursive payload validator. This slice should establish the only outbound path to Groq Cloud, enforce the patient-data ban before any request is sent, apply the global concurrency limit, and emit structured call logs with feature, input-token estimate, and duration.

### Acceptance criteria

- [ ] The Grok client can make standard chat-completion requests and return assistant text.
- [ ] The Grok client can stream chat-completion output incrementally.
- [ ] Grok calls are limited by a process-wide concurrency cap.
- [ ] Requests containing forbidden fields are rejected before any external API call is attempted.
- [ ] Upstream Grok failures are mapped to a service-unavailable error contract.
- [ ] Each Grok call emits a structured log entry with feature name, estimated input tokens, and duration.

---

## Phase 3: Explanation Endpoint

**User stories**: 1, 2, 3, 5, 8, 16

### What to build

Add `POST /llm/explain` as the first production endpoint. It should accept pharmacist-facing forecast context from Spring Boot, validate the payload, build the explanation prompt, call Grok, and return a generated explanation plus a timestamp.

### Acceptance criteria

- [ ] The endpoint accepts the required explanation request schema.
- [ ] The endpoint validates the payload before prompt construction or Grok access.
- [ ] The generated prompt stays focused on aggregated drug-level forecast and inventory context.
- [ ] The response returns generated explanation text and an ISO-8601 `generated_at` timestamp.
- [ ] The response contract is stable enough for Spring Boot to consume directly.

---

## Phase 4: Streaming Chat Endpoint

**User stories**: 4, 5, 8, 9, 10, 13, 14

### What to build

Add `POST /llm/chat` with streamed output. This slice should prepend the system prompt, forward the message history, validate the payload, and return Server-Sent Events that deliver token chunks in order followed by a final completion event.

### Acceptance criteria

- [ ] The endpoint accepts the required chat request schema.
- [ ] Patient-data validation runs before any streaming call begins.
- [ ] The response is `text/event-stream`.
- [ ] Each emitted SSE event contains a token payload in the documented shape.
- [ ] The stream ends with a final done event that includes an estimated total token count.

---

## Phase 5: Purchase-Order Endpoint

**User stories**: 6, 7, 8, 9, 15, 16

### What to build

Add `POST /llm/purchase-order` for drafting ordering text from pharmacy and drug context. This slice should validate the payload, build the order-generation prompt, call Grok, and return generated order text with a timestamp.

### Acceptance criteria

- [ ] The endpoint accepts the required purchase-order request schema.
- [ ] The endpoint validates the payload before prompt construction or Grok access.
- [ ] The prompt uses only operational pharmacy and drug data.
- [ ] The response returns generated order text and an ISO-8601 `generated_at` timestamp.
- [ ] The endpoint is usable as a text-generation boundary for Spring Boot ordering flows.

---

## Phase 6: Contract Tests and Guardrails

**User stories**: all of the above

### What to build

Add tests that verify the public API behavior, error mapping, safety guardrails, and stream shape. This slice should prove the service boundary without coupling tests to internal implementation details.

### Acceptance criteria

- [ ] There are endpoint tests for explanation, chat streaming, and purchase-order generation.
- [ ] Tests cover recursive rejection of forbidden patient-related fields.
- [ ] Tests cover Grok success and upstream failure cases with mocked HTTP responses.
- [ ] Tests verify the SSE stream shape and the final done event.
- [ ] Tests verify the service remains separated from forecasting and Supabase concerns.
