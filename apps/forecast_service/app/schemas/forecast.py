from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class ForecastPlaceholder(BaseModel):
    ready: bool = False


class SupplementalHistoryPoint(BaseModel):
    week: str
    quantity: int = Field(ge=0)


class DrugForecastRequest(BaseModel):
    location_id: str
    din: str
    horizon_days: Literal[7, 14, 30] = 7
    quantity_on_hand: int = Field(..., ge=0)
    lead_time_days: int = Field(default=2, ge=1)
    safety_multiplier: Literal[1.5, 1.0, 0.75] = 1.0
    red_threshold_days: int = Field(default=3, ge=1)
    amber_threshold_days: int = Field(default=7, ge=1)
    supplemental_history: Optional[list[SupplementalHistoryPoint]] = None


class ForecastThreshold(BaseModel):
    lead_time_days: int = Field(default=2, ge=1)
    safety_multiplier: Literal[1.5, 1.0, 0.75] = 1.0
    red_threshold_days: int = Field(default=3, ge=1)
    amber_threshold_days: int = Field(default=7, ge=1)


class BatchForecastRequest(BaseModel):
    location_id: str
    dins: list[str] = Field(min_length=1)
    horizon_days: Literal[7, 14, 30]
    thresholds: Dict[str, ForecastThreshold]


class NotificationCheckRequest(BaseModel):
    location_id: str
