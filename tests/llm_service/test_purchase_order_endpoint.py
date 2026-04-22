from fastapi.testclient import TestClient

from apps.llm_service.app.main import app


def test_purchase_order_endpoint_returns_order_text(monkeypatch):
    captured = {}

    async def fake_call_grok(messages, max_tokens):
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        return "Order Amoxicillin 500 mg and keep a two-week buffer."

    monkeypatch.setattr("shared.grok_client.call_grok", fake_call_grok)

    client = TestClient(app)

    response = client.post(
        "/llm/purchase-order",
        json={
            "pharmacy_name": "Downtown Pharmacy",
            "location_address": "123 Bank St, Ottawa, ON",
            "today": "2026-04-21",
            "horizon_days": 14,
            "drugs": [
                {
                    "drug_name": "Amoxicillin",
                    "strength": "500 mg",
                    "din": "12345678",
                    "current_stock": 8,
                    "predicted_quantity": 40,
                    "days_of_supply": 2.5,
                    "reorder_status": "RED",
                    "avg_daily_demand": 3.1,
                    "lead_time_days": 2,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["order_text"] == "Order Amoxicillin 500 mg and keep a two-week buffer."
    assert payload["generated_at"].endswith("+00:00")
    assert captured["max_tokens"] == 1500
    assert captured["messages"][0]["role"] == "system"
    assert "Downtown Pharmacy" in captured["messages"][0]["content"]
    assert "Amoxicillin 500 mg" in captured["messages"][0]["content"]


def test_purchase_order_endpoint_rejects_patient_data():
    client = TestClient(app)

    response = client.post(
        "/llm/purchase-order",
        json={
            "pharmacy_name": "Downtown Pharmacy",
            "location_address": "123 Bank St, Ottawa, ON",
            "today": "2026-04-21",
            "horizon_days": 14,
            "drugs": [
                {
                    "drug_name": "Amoxicillin",
                    "strength": "500 mg",
                    "din": "12345678",
                    "current_stock": 8,
                    "predicted_quantity": 40,
                    "days_of_supply": 2.5,
                    "reorder_status": "RED",
                    "avg_daily_demand": 3.1,
                    "lead_time_days": 2,
                    "patient_id": "abc123",
                }
            ],
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "INVALID_PAYLOAD",
        "message": "Patient data is not permitted in LLM requests",
    }
