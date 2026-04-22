from datetime import datetime

from fastapi.testclient import TestClient

from apps.llm_service.app.main import app


def test_explain_endpoint_returns_explanation_and_timestamp(monkeypatch):
    captured = {}

    async def fake_call_grok(messages, max_tokens):
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        return "The drug is trending upward, so reorder now."

    monkeypatch.setattr("shared.grok_client.call_grok", fake_call_grok)

    client = TestClient(app)

    response = client.post(
        "/llm/explain",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "drug_name": "Amoxicillin",
            "strength": "500 mg",
            "therapeutic_class": "Antibiotic",
            "quantity_on_hand": 15,
            "days_of_supply": 4.5,
            "avg_daily_demand": 3.2,
            "horizon_days": 14,
            "predicted_quantity": 45,
            "prophet_lower": 40,
            "prophet_upper": 51,
            "confidence": "HIGH",
            "reorder_status": "RED",
            "reorder_point": 12.0,
            "lead_time_days": 2,
            "data_points_used": 28,
            "weekly_quantities": [4, 5, 6, 7, 8, 9, 10, 11],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["explanation"] == "The drug is trending upward, so reorder now."
    assert payload["generated_at"].endswith("+00:00")
    datetime.fromisoformat(payload["generated_at"])
    assert captured["max_tokens"] == 600
    assert captured["messages"][0]["role"] == "system"
    assert "Amoxicillin 500 mg" in captured["messages"][0]["content"]
    assert "Current inventory: 15 units" in captured["messages"][0]["content"]
    assert captured["messages"][1]["role"] == "user"


def test_explain_endpoint_rejects_patient_data():
    client = TestClient(app)

    response = client.post(
        "/llm/explain",
        json={
            "location_id": "11111111-1111-1111-1111-111111111111",
            "din": "12345678",
            "drug_name": "Amoxicillin",
            "strength": "500 mg",
            "therapeutic_class": "Antibiotic",
            "quantity_on_hand": 15,
            "days_of_supply": 4.5,
            "avg_daily_demand": 3.2,
            "horizon_days": 14,
            "predicted_quantity": 45,
            "prophet_lower": 40,
            "prophet_upper": 51,
            "confidence": "HIGH",
            "reorder_status": "RED",
            "reorder_point": 12.0,
            "lead_time_days": 2,
            "data_points_used": 28,
            "weekly_quantities": [4, 5, 6, 7, 8, 9, 10, 11],
            "patient_id": "abc123",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "INVALID_PAYLOAD",
        "message": "Patient data is not permitted in LLM requests",
    }
