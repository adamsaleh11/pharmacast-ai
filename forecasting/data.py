from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from forecasting.exceptions import BacktestLeakageError, BacktestSchemaError


REQUIRED_COLUMNS = {"dispensed_date", "din", "quantity_dispensed"}
OPTIONAL_COLUMNS = {"quantity_on_hand", "cost_per_unit", "patient_id"}
FORECAST_COLUMN_ORDER = [
    "run_id",
    "model_version",
    "backtest_name",
    "generated_at",
    "din",
    "forecast_date",
    "yhat",
    "yhat_lower",
    "yhat_upper",
    "actual_quantity",
    "train_start_date",
    "train_end_date",
    "horizon_length",
    "history_points_used",
    "model_path",
    "confidence_label",
    "anomaly_flag",
    "anomaly_reason",
]


@dataclass(frozen=True)
class LoadedCsv:
    frame: pd.DataFrame
    source_path: Path


def load_input_csv(path: str | Path) -> pd.DataFrame:
    """Load a backtest input CSV and validate the canonical schema."""

    source_path = Path(path)
    if not source_path.is_file():
        raise BacktestSchemaError(f"missing_input_file:{source_path}")

    frame = pd.read_csv(source_path)
    validate_input_frame(frame, source_path)
    return normalize_input_frame(frame)


def validate_input_frame(frame: pd.DataFrame, source_path: Path | None = None) -> None:
    """Validate that a backtest input frame has the required columns and values."""

    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        label = f" in {source_path}" if source_path else ""
        raise BacktestSchemaError(f"missing_required_columns{label}:{sorted(missing)}")

    if frame[["dispensed_date", "din", "quantity_dispensed"]].isna().any().any():
        raise BacktestSchemaError("required_values_must_not_be_null")
    if frame["din"].astype(str).str.strip().eq("").any():
        raise BacktestSchemaError("blank_din")

    try:
        pd.to_datetime(frame["dispensed_date"], format="%Y-%m-%d", errors="raise")
    except Exception as exc:  # pragma: no cover - pandas error message varies
        raise BacktestSchemaError("invalid_dispensed_date_format") from exc

    try:
        converted = pd.to_numeric(frame["quantity_dispensed"], errors="coerce")
        if converted.isna().any():
            raise ValueError("invalid quantity_dispensed")
    except Exception as exc:  # pragma: no cover - pandas error message varies
        raise BacktestSchemaError("invalid_quantity_dispensed") from exc

    if "quantity_on_hand" in frame.columns:
        try:
            converted = pd.to_numeric(frame["quantity_on_hand"], errors="coerce")
            invalid = frame["quantity_on_hand"].notna() & converted.isna()
            if invalid.any():
                raise ValueError("invalid quantity_on_hand")
        except Exception as exc:  # pragma: no cover - defensive
            raise BacktestSchemaError("invalid_quantity_on_hand") from exc

    if "cost_per_unit" in frame.columns:
        try:
            converted = pd.to_numeric(frame["cost_per_unit"], errors="coerce")
            invalid = frame["cost_per_unit"].notna() & converted.isna()
            if invalid.any():
                raise ValueError("invalid cost_per_unit")
        except Exception as exc:  # pragma: no cover - defensive
            raise BacktestSchemaError("invalid_cost_per_unit") from exc


def normalize_input_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized copy of the input frame with stable types."""

    normalized = frame.copy()
    normalized["dispensed_date"] = pd.to_datetime(normalized["dispensed_date"], format="%Y-%m-%d").dt.date
    normalized["din"] = normalized["din"].astype(str).str.strip()
    normalized["quantity_dispensed"] = pd.to_numeric(normalized["quantity_dispensed"], errors="raise")

    for column in OPTIONAL_COLUMNS:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    for column in OPTIONAL_COLUMNS - set(normalized.columns):
        normalized[column] = pd.NA

    if "patient_id" in normalized.columns:
        normalized["patient_id"] = normalized["patient_id"].astype("string")

    normalized = normalized.sort_values(["din", "dispensed_date"]).reset_index(drop=True)
    return normalized


def validate_no_leakage(train_frame: pd.DataFrame, actual_frame: pd.DataFrame) -> None:
    """Fail when the training and actual sets overlap on din/date pairs."""

    train_pairs = set(zip(train_frame["din"].astype(str), train_frame["dispensed_date"].astype(str)))
    actual_pairs = set(zip(actual_frame["din"].astype(str), actual_frame["dispensed_date"].astype(str)))
    overlap = sorted(train_pairs & actual_pairs)
    if overlap:
        raise BacktestLeakageError(f"training_actual_overlap:{overlap[:5]}")


def aggregate_weekly(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw rows to the weekly Monday buckets used by the forecasting model."""

    if frame.empty:
        return frame.copy()

    from apps.forecast_service.app.services.history import week_start_monday

    grouped_rows: list[dict[str, Any]] = []
    working = frame.copy()
    working["week_start"] = working["dispensed_date"].map(week_start_monday)
    aggregations = {"quantity_dispensed": "sum"}
    if "quantity_on_hand" in working.columns:
        aggregations["quantity_on_hand"] = "last"
    if "cost_per_unit" in working.columns:
        aggregations["cost_per_unit"] = "last"
    if "patient_id" in working.columns:
        aggregations["patient_id"] = "first"

    grouped = (
        working.groupby(["din", "week_start"], as_index=False)
        .agg(aggregations)
        .rename(columns={"week_start": "dispensed_date"})
        .sort_values(["din", "dispensed_date"])
        .reset_index(drop=True)
    )
    return grouped


def load_stock_levels(path: str | Path | None) -> dict[str, float] | None:
    """Load optional stock levels for stockout risk evaluation."""

    if path is None:
        return None

    source_path = Path(path)
    if not source_path.is_file():
        raise BacktestSchemaError(f"missing_stock_level_file:{source_path}")

    frame = pd.read_csv(source_path)
    required = {"din", "quantity_on_hand"}
    missing = required - set(frame.columns)
    if missing:
        raise BacktestSchemaError(f"missing_stock_level_columns:{sorted(missing)}")

    stock_levels: dict[str, float] = {}
    for row in frame.to_dict(orient="records"):
        din = str(row["din"]).strip()
        if not din:
            raise BacktestSchemaError("blank_stock_level_din")
        try:
            quantity = float(row["quantity_on_hand"])
        except Exception as exc:  # pragma: no cover - defensive
            raise BacktestSchemaError("invalid_stock_level_quantity") from exc
        if pd.isna(quantity):
            raise BacktestSchemaError("invalid_stock_level_quantity")
        stock_levels[din] = quantity
    return stock_levels
