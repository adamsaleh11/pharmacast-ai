from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def ensure_output_dir(path: str | Path) -> Path:
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def write_dataframe_artifacts(frame: pd.DataFrame, csv_path: Path, json_path: Path | None = None) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    if json_path is not None:
        sanitized = frame.where(pd.notna(frame), None)
        json_path.write_text(
            json.dumps(sanitized.to_dict(orient="records"), indent=2, default=json_default, sort_keys=True)
        )


def write_json_artifact(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=json_default, sort_keys=True))
