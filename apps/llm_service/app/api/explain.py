from datetime import datetime, timezone

from fastapi import APIRouter

import shared.grok_client as grok_client
from apps.llm_service.app.schemas.explain import ExplainRequest, ExplainResponse
from shared.validators import validate_no_patient_data


router = APIRouter(prefix="/explain", tags=["llm"])


def _build_explain_messages(request: ExplainRequest) -> list[dict[str, str]]:
    prompt = f"""
You are a pharmacy inventory advisor helping an independent pharmacist in Ottawa,
Canada understand their drug demand forecast.

Drug: {request.drug_name} {request.strength} (DIN: {request.din})
Therapeutic class: {request.therapeutic_class}

Current inventory: {request.quantity_on_hand} units (pharmacist-entered count)
Days of supply remaining: {request.days_of_supply} days
Average daily dispensing: {request.avg_daily_demand} units/day

Forecast for next {request.horizon_days} days: {request.predicted_quantity} units
(range: {request.prophet_lower}–{request.prophet_upper})
Confidence: {request.confidence}
Reorder status: {request.reorder_status}
Reorder point: {request.reorder_point} units
Lead time from supplier: {request.lead_time_days} days
Weeks of dispensing history used: {request.data_points_used}

Recent dispensing trend (last 8 weeks, oldest to newest): {request.weekly_quantities}

Write a 3–4 sentence explanation for the pharmacist covering:
1. Why the system recommends this reorder status
2. What the dispensing trend shows
3. One specific action they should take today

Rules:
- Be direct and specific. Reference actual numbers.
- Use plain language — no jargon.
- Do NOT mention Prophet, AI, algorithms, or machine learning.
- Write as an experienced pharmacy supply advisor, not a software system.
""".strip()
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Write the explanation now."},
    ]


@router.post("", response_model=ExplainResponse)
async def explain(request: ExplainRequest) -> ExplainResponse:
    validate_no_patient_data(request.model_dump())
    messages = _build_explain_messages(request)
    with grok_client.feature_context("explain"):
        explanation = await grok_client.call_grok(messages, max_tokens=600)
    return ExplainResponse(
        explanation=explanation,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
