from pydantic import Field

from apps.llm_service.app.schemas.common import AllowExtraModel


class ExplainRequest(AllowExtraModel):
    location_id: str
    din: str
    drug_name: str
    strength: str
    therapeutic_class: str
    quantity_on_hand: int = Field(ge=0)
    days_of_supply: float
    avg_daily_demand: float
    horizon_days: int
    predicted_quantity: int
    prophet_lower: int
    prophet_upper: int
    confidence: str
    reorder_status: str
    reorder_point: float
    lead_time_days: int
    data_points_used: int
    weekly_quantities: list[int]


class ExplainResponse(AllowExtraModel):
    explanation: str
    generated_at: str
