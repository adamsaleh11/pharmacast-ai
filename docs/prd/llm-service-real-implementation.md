## Problem Statement

PharmaForecast needs a dedicated language-generation service for pharmacist-facing explanations, chat responses, and purchase-order drafting. Today, the `llm_service` boundary exists only as a placeholder, so Spring Boot has no real Python endpoint it can call when it needs natural-language output derived from forecast context.

This matters now because the product already depends on clear separation between numeric forecasting and language generation. The LLM service must stay isolated from forecasting code, must never read directly from Supabase, and must enforce the compliance rule that patient identifiers never leave the backend boundary or appear in prompts, logs, exports, or generated documents.

## Solution

Build a real FastAPI `llm_service` that talks only to the Groq Cloud OpenAI-compatible API and exposes three public endpoints:

- `POST /llm/explain` for pharmacist-facing forecast explanations
- `POST /llm/chat` for streamed chat responses
- `POST /llm/purchase-order` for drafted purchase-order text

The service will receive all necessary context from Spring Boot, validate that no patient data fields are present anywhere in the payload, and generate language output using one configurable Grok model for all endpoints. The service will not perform forecasting, will not query Supabase, and will not contain Prophet or other numeric-model code. Its responsibility is strictly natural-language generation from already-aggregated operational data.

## User Stories

1. As a pharmacist, I want to ask why a drug is flagged for reorder, so that I can understand the recommendation before acting on it.
2. As a pharmacist, I want the explanation to reference actual inventory, demand, and forecast numbers, so that I can judge whether the recommendation matches what I see on the shelf.
3. As a pharmacist, I want the explanation to avoid jargon and model names, so that it reads like advice from a supply expert rather than a technical report.
4. As a pharmacy owner, I want chat responses to stream token by token, so that the interface feels responsive while longer answers are generated.
5. As a pharmacist, I want chat requests to reject any patient-level fields, so that regulated personal data never reaches the language model.
6. As an operations user, I want purchase-order drafts to be generated from the same service, so that ordering text stays consistent with forecast and inventory context.
7. As a pharmacy owner, I want purchase-order text to use the pharmacy’s own name, address, and inventory context, so that the draft is immediately usable.
8. As a backend engineer, I want Spring Boot to remain the source of all context sent to the LLM service, so that the Python service does not need direct database access.
9. As a compliance reviewer, I want the LLM service to reject payloads containing patient identifiers, so that patient data never enters an external API request.
10. As a compliance reviewer, I want the service to check nested objects and lists for forbidden fields, so that hidden patient data cannot bypass validation.
11. As a platform engineer, I want one default Grok model for the whole service, so that configuration stays simple and behavior stays consistent across endpoints.
12. As a platform engineer, I want the Grok model to be configurable through an environment variable, so that the service can be tuned without code changes.
13. As a platform engineer, I want concurrent Grok calls to be limited, so that the service remains stable under bursty traffic.
14. As a backend integrator, I want clear error responses when Grok is unavailable, so that the UI and Spring Boot can recover gracefully.
15. As a backend integrator, I want clear error responses when a forbidden field is detected, so that bad payloads fail fast and are easy to diagnose.
16. As a pharmacy owner, I want the explanation and order-drafting outputs to stay Canada-focused, so that the service language aligns with the product’s operating context.
17. As a developer, I want the service to log each Grok call with feature name, estimated input tokens, and duration, so that usage and latency can be monitored.
18. As a developer, I want the LLM service to remain separate from the forecasting service, so that language and numeric behavior can evolve independently.

## Implementation Decisions

- Create a standalone FastAPI `llm_service` package that is separate from the forecasting service package.
- Add a shared Groq client module that is the only code path for calling Groq Cloud.
- Configure the Groq client with a single base URL, one model name, a fixed temperature, and a process-wide concurrency limit of 10 in-flight requests.
- Use `GROQ_API_KEY` for authentication and `GROQ_MODEL` for model selection, with a single default model for all endpoints.
- Use `openai/gpt-oss-120b` as the default model for this service.
- Implement both standard completion calls and streaming completion calls against Grok’s chat-completions API.
- Return the assistant text from Grok directly for non-streaming requests.
- Stream chat responses back to the caller as Server-Sent Events with one token payload per event and a final completion event.
- Validate every endpoint request with a recursive patient-data guard before any Grok call is made.
- Treat the forbidden field set as `patient_id`, `patient_name`, `patient_dob`, `prescriber_id`, and `prescriber_name`.
- Make the forbidden-field validation recursive across nested dictionaries and lists.
- Return a 503-style service-unavailable response when Groq is unavailable or returns an upstream error.
- Return a 400-style invalid-payload response when forbidden patient data is detected.
- Keep all prompt content focused on aggregated drug-level operational data only.
- For `explain`, build a concise pharmacist-facing prompt that references current inventory, days of supply, average daily demand, forecast range, confidence, reorder status, reorder point, lead time, and recent weekly dispensing history.
- For `chat`, prepend the supplied system prompt and stream the supplied message history to Grok without adding any patient-level data.
- For `purchase-order`, build an order-drafting prompt from pharmacy name, location address, date, horizon, and the list of drugs with operational stock and forecast context.
- Do not read from Supabase in this service; Spring Boot remains the data and orchestration owner.
- Do not add Prophet, forecasting logic, or numeric demand computation to this service.
- Keep the service API contract limited to the request/response shapes needed for explanation, chat, and purchase-order generation.
- Use ISO-8601 timestamps for generated response metadata.

## Testing Decisions

- Test the service through its public FastAPI endpoints rather than internal helper behavior.
- Test that `POST /llm/explain` validates patient-data-free payloads and returns a generated explanation and timestamp.
- Test that `POST /llm/chat` emits well-formed SSE events and a final done event.
- Test that `POST /llm/purchase-order` returns generated order text and timestamp.
- Test that forbidden fields are rejected even when they appear nested inside lists or dictionaries.
- Test the Grok client behavior with mocked HTTP responses, including normal completions, streamed completions, and upstream failure handling.
- Test the exception mapping so Grok errors return the service-unavailable shape and validation errors return the invalid-payload shape.
- Use existing FastAPI and service boundary tests in the repo as prior art for contract-focused testing.

## Out of Scope

- Forecasting, Prophet, or any numeric demand modeling.
- Supabase reads, writes, or authentication.
- Spring Boot implementation work.
- Frontend integration work.
- Any use of patient identifiers in prompts, logs, exports, generated documents, or external requests.
- Tool calling, function calling, or multi-model routing.
- Auto-retry, fallback-model, or circuit-breaker behavior beyond the basic service-unavailable response.
- Persistent chat history storage.
- Purchase-order submission workflows outside text generation.

## Further Notes

- The model should be selected once and used consistently across all LLM endpoints; the default should be set through configuration, not hard-coded in endpoint logic.
- The service should treat prompt content as sensitive operational output and keep it aligned to aggregated drug-level data only.
- Spring Boot must continue to own ownership checks, tenant isolation, and payload assembly before calling this service.
- The next planning step should break this PRD into implementation slices for dependency setup, Grok client, payload validation, endpoint wiring, streaming behavior, and contract tests.
