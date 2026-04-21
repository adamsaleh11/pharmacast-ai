from datetime import datetime

from fastapi.testclient import TestClient

from apps.forecast_service.app.main import app


class _SpringContractEngine:
    def forecast_drug(self, _request):
        return {
            "din": "02230711",
            "location_id": "b098e4c4-e499-45d0-aadc-86edfdac555b",
            "horizon_days": 21,
            "predicted_quantity": 42,
            "prophet_lower": 38,
            "prophet_upper": 47,
            "confidence": "HIGH",
            "days_of_supply": 10.5,
            "avg_daily_demand": 6.0,
            "reorder_status": "GREEN",
            "reorder_point": 18.0,
            "generated_at": "2026-04-21T19:03:23Z",
            "data_points_used": 21,
            "model_path": "prophet",
            "patient_id": "patient-123",
        }


def test_post_forecast_drug_matches_spring_contract(monkeypatch):
    from apps.forecast_service.app.services import forecasting

    monkeypatch.setattr(forecasting, "get_default_engine", lambda: _SpringContractEngine())

    client = TestClient(app)

    response = client.post(
        "/forecast/drug",
        json={
            "location_id": "b098e4c4-e499-45d0-aadc-86edfdac555b",
            "din": "02230711",
            "horizon_days": 21,
            "quantity_on_hand": 80,
            "lead_time_days": 2,
            "safety_multiplier": 1.25,
            "red_threshold_days": 3,
            "amber_threshold_days": 7,
            "supplemental_history": [
                {
                    "week_start": "2026-04-13",
                    "quantity": 5,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["x-forecast-code-path"] == "weekly-xgboost-residual-v1"

    payload = response.json()
    assert payload == {
        "din": "02230711",
        "location_id": "b098e4c4-e499-45d0-aadc-86edfdac555b",
        "horizon_days": 21,
        "predicted_quantity": 42,
        "prophet_lower": 38,
        "prophet_upper": 47,
        "confidence": "HIGH",
        "days_of_supply": 10.5,
        "avg_daily_demand": 6.0,
        "reorder_status": "GREEN",
        "reorder_point": 18.0,
        "generated_at": "2026-04-21T19:03:23Z",
        "data_points_used": 21,
        "model_path": "prophet",
    }

    datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
    assert "patient_id" not in response.text
