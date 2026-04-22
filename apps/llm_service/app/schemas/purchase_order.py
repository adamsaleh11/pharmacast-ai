from pydantic import Field

from apps.llm_service.app.schemas.common import AllowExtraModel


class PurchaseOrderDrug(AllowExtraModel):
    drug_name: str
    strength: str
    din: str
    current_stock: int = Field(ge=0)
    predicted_quantity: int
    days_of_supply: float
    reorder_status: str
    avg_daily_demand: float
    lead_time_days: int


class PurchaseOrderRequest(AllowExtraModel):
    pharmacy_name: str
    location_address: str
    today: str
    horizon_days: int
    drugs: list[PurchaseOrderDrug]


class PurchaseOrderResponse(AllowExtraModel):
    order_text: str
    generated_at: str
