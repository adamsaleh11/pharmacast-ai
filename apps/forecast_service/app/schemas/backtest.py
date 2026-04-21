from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BacktestDemandRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispensed_date: str
    din: str
    quantity_dispensed: float = Field(ge=0)
    cost_per_unit: Optional[float] = None


class BacktestUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str
    location_id: str
    csv_upload_id: str
    model_version: str = "prophet_v1"
    rows: list[BacktestDemandRow] = Field(min_length=1)
    debug_artifacts: bool = False


class BacktestUploadSummary(BaseModel):
    status: Literal["PASS", "LOW_CONFIDENCE", "FAIL", "ERROR"]
    model_version: str
    mae: Optional[float] = None
    wape: Optional[float] = None
    interval_coverage: Optional[float] = None
    anomaly_count: Optional[int] = None
    beats_last_7_day_avg: Optional[bool] = None
    beats_last_14_day_avg: Optional[bool] = None
    baseline_last_7_day_avg_mae: Optional[float] = None
    baseline_last_14_day_avg_mae: Optional[float] = None
    rows_evaluated: Optional[int] = None
    raw_rows_received: Optional[int] = None
    usable_rows: Optional[int] = None
    min_required_rows: Optional[int] = None
    date_range: Optional[dict[str, Optional[str]]] = None
    ready_for_forecast: bool = False
    din_count: Optional[int] = None
    generated_at: str
    error_message: Optional[str] = None
    artifact_path: Optional[str] = None
