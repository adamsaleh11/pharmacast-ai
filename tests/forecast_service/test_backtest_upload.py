import pandas as pd
from fastapi.testclient import TestClient

from apps.forecast_service.app.main import app


def _fixture_rows():
    frame = pd.read_csv("pharmaforecast_backtesting/pharmaforecast_test_dispensing_v2 copy.csv", dtype={"din": str})
    return frame.to_dict(orient="records")


def test_backtest_upload_returns_pass_summary_for_uploaded_fixture():
    client = TestClient(app)

    response = client.post(
        "/backtest/upload",
        json={
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "location_id": "22222222-2222-2222-2222-222222222222",
            "csv_upload_id": "33333333-3333-3333-3333-333333333333",
            "model_version": "prophet_v1",
            "debug_artifacts": False,
            "rows": _fixture_rows(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PASS"
    assert payload["model_version"] == "prophet_v1"
    assert payload["mae"] < payload["baseline_last_7_day_avg_mae"]
    assert payload["mae"] < payload["baseline_last_14_day_avg_mae"]
    assert payload["wape"] <= 0.2
    assert payload["interval_coverage"] >= 0.75
    assert payload["anomaly_count"] == 0
    assert payload["beats_last_7_day_avg"] is True
    assert payload["beats_last_14_day_avg"] is True
    assert payload["rows_evaluated"] > 0
    assert payload["raw_rows_received"] == 100
    assert payload["usable_rows"] == 100
    assert payload["min_required_rows"] == 8
    assert payload["date_range"] == {"start": "2025-12-01", "end": "2026-04-13"}
    assert payload["ready_for_forecast"] is True
    assert payload["din_count"] == 5
    assert payload["artifact_path"] is None
    assert payload["generated_at"].endswith("+00:00")


def test_backtest_upload_rejects_patient_identifiers():
    rows = _fixture_rows()
    rows[0]["patient_id"] = "patient-123"
    client = TestClient(app)

    response = client.post(
        "/backtest/upload",
        json={
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "location_id": "22222222-2222-2222-2222-222222222222",
            "csv_upload_id": "33333333-3333-3333-3333-333333333333",
            "model_version": "prophet_v1",
            "rows": rows,
        },
    )

    assert response.status_code == 422
    assert "patient_id" in response.text


def test_backtest_upload_returns_fail_summary_for_insufficient_history():
    client = TestClient(app)

    response = client.post(
        "/backtest/upload",
        json={
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "location_id": "22222222-2222-2222-2222-222222222222",
            "csv_upload_id": "33333333-3333-3333-3333-333333333333",
            "model_version": "prophet_v1",
            "rows": [
                {
                    "dispensed_date": "2026-01-05",
                    "din": "02431327",
                    "quantity_dispensed": 54,
                    "cost_per_unit": 0.55,
                },
                {
                    "dispensed_date": "2026-01-12",
                    "din": "02431327",
                    "quantity_dispensed": 57,
                    "cost_per_unit": 0.55,
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "FAIL",
        "model_version": "prophet_v1",
        "mae": None,
        "wape": None,
        "interval_coverage": None,
        "anomaly_count": None,
        "beats_last_7_day_avg": None,
        "beats_last_14_day_avg": None,
        "baseline_last_7_day_avg_mae": None,
        "baseline_last_14_day_avg_mae": None,
        "rows_evaluated": 0,
        "raw_rows_received": 2,
        "usable_rows": 2,
        "min_required_rows": 8,
        "date_range": {"start": "2026-01-05", "end": "2026-01-12"},
        "ready_for_forecast": False,
        "din_count": 1,
        "generated_at": response.json()["generated_at"],
        "error_message": "insufficient_backtest_history",
        "artifact_path": None,
    }
