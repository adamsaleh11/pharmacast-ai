from fastapi.testclient import TestClient

from apps.llm_service.app.main import app
from apps.llm_service.app.services.chat_policy import PHARMACY_CHAT_POLICY
from shared import grok_client


def test_chat_endpoint_streams_sse_events(monkeypatch):
    async def fake_stream_grok(messages, max_tokens):
        assert messages[0]["role"] == "system"
        assert PHARMACY_CHAT_POLICY in messages[0]["content"]
        assert "You are a helpful assistant." in messages[0]["content"]
        assert max_tokens == 2000
        yield "Hel"
        yield "lo"

    monkeypatch.setattr("shared.grok_client.stream_grok", fake_stream_grok)

    client = TestClient(app)

    with client.stream(
        "POST",
        "/llm/chat",
        json={
            "system_prompt": "You are a helpful assistant.",
            "messages": [{"role": "user", "content": "Say hello"}],
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'data: {"token": "Hel"}' in body
    assert 'data: {"token": "lo"}' in body
    assert 'data: {"done": true, "total_tokens": 1}' in body


def test_chat_policy_explicitly_blocks_unrelated_topics():
    assert "NHL" in PHARMACY_CHAT_POLICY
    assert "do not answer the question" in PHARMACY_CHAT_POLICY
    assert "pharmacy operations" in PHARMACY_CHAT_POLICY
    assert "any other pharmacy" in PHARMACY_CHAT_POLICY
    assert "Other pharmacies are strictly off-limits" in PHARMACY_CHAT_POLICY


def test_chat_endpoint_rejects_nested_patient_data():
    client = TestClient(app)

    response = client.post(
        "/llm/chat",
        json={
            "system_prompt": "You are a helpful assistant.",
            "messages": [
                {
                    "role": "user",
                    "content": "Say hello",
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


def test_chat_endpoint_streams_sse_error_when_grok_fails_during_stream(monkeypatch):
    async def fake_stream_grok(messages, max_tokens):
        yield "Hel"
        raise grok_client.GrokApiException(429, "rate limit")

    monkeypatch.setattr("shared.grok_client.stream_grok", fake_stream_grok)

    client = TestClient(app)

    with client.stream(
        "POST",
        "/llm/chat",
        json={
            "system_prompt": "You are a helpful assistant.",
            "messages": [{"role": "user", "content": "Say hello"}],
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert 'data: {"token": "Hel"}' in body
    assert 'data: {"error": "LLM_UNAVAILABLE", "message": "Try again in a moment"}' in body
    assert "Traceback" not in body
    assert "rate limit" not in body
