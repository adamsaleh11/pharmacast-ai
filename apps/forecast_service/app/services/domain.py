from __future__ import annotations

from dataclasses import dataclass


class ForecastingError(Exception):
    pass


@dataclass(frozen=True)
class ForecastPrediction:
    predicted_quantity: int
    prophet_lower: int
    prophet_upper: int
    confidence: str


@dataclass(frozen=True)
class ForecastResult:
    din: str
    location_id: str
    horizon_days: int
    predicted_quantity: int
    prophet_lower: int
    prophet_upper: int
    confidence: str
    days_of_supply: float
    avg_daily_demand: float
    reorder_status: str
    reorder_point: float
    generated_at: str
    data_points_used: int
