from datetime import date
from typing import Dict, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ForecastPlaceholder(BaseModel):
    ready: bool = False


class SupplementalHistoryPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    week_start: date = Field(validation_alias=AliasChoices("week_start", "week"), serialization_alias="week_start")
    quantity: int = Field(ge=0)


class DrugForecastRequest(BaseModel):
    location_id: str
    din: str
    horizon_days: int = Field(default=7, ge=1)
    quantity_on_hand: int = Field(..., ge=0)
    lead_time_days: int = Field(default=2, ge=1)
    safety_multiplier: float = Field(default=1.0, gt=0)
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
