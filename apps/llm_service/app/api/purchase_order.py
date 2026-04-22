from datetime import datetime, timezone

from fastapi import APIRouter

import shared.grok_client as grok_client
from apps.llm_service.app.schemas.purchase_order import (
    PurchaseOrderRequest,
    PurchaseOrderResponse,
)
from shared.validators import validate_no_patient_data


router = APIRouter(prefix="/purchase-order", tags=["llm"])


def _build_purchase_order_messages(request: PurchaseOrderRequest) -> list[dict[str, str]]:
    drug_lines = "\n".join(
        [
            (
                f"- {drug.drug_name} {drug.strength} (DIN: {drug.din}): "
                f"current stock {drug.current_stock}, predicted quantity {drug.predicted_quantity}, "
                f"days of supply {drug.days_of_supply}, reorder status {drug.reorder_status}, "
                f"average daily demand {drug.avg_daily_demand}, lead time {drug.lead_time_days} days"
            )
            for drug in request.drugs
        ]
    )
    prompt = f"""
You are a pharmacy inventory advisor drafting a purchase order for an independent
pharmacy in Ottawa, Canada.

Pharmacy name: {request.pharmacy_name}
Location address: {request.location_address}
Today: {request.today}
Forecast horizon: {request.horizon_days} days

Drugs:
{drug_lines}

Write a clear purchase-order draft that:
- groups the drugs into an order-ready list
- references the operational reason for each line item
- uses plain language a pharmacist can review quickly
- does not mention patient data, models, or internal system details
""".strip()
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Draft the purchase order now."},
    ]


@router.post("", response_model=PurchaseOrderResponse)
async def purchase_order(request: PurchaseOrderRequest) -> PurchaseOrderResponse:
    validate_no_patient_data(request.model_dump())
    messages = _build_purchase_order_messages(request)
    with grok_client.feature_context("purchase_order"):
        order_text = await grok_client.call_grok(messages, max_tokens=1500)
    return PurchaseOrderResponse(
        order_text=order_text,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
