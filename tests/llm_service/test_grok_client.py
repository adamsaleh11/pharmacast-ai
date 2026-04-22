import httpx
import pytest
import anyio

import shared.grok_client as grok_client


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.reason_phrase = "Bad Gateway"
        self.request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=self.request,
                response=httpx.Response(self.status_code, text=self.text, request=self.request),
            )

    def json(self):
        return self._json_data


class _FakeStreamContext:
    def __init__(self, lines, response):
        self._lines = lines
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeStreamResponse(_FakeResponse):
    def __init__(self, lines):
        super().__init__(200, {})
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeAsyncClient:
    last_request = None
    last_stream_request = None

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, path, headers=None, json=None):
        self.__class__.last_request = {"path": path, "headers": headers, "json": json}
        return _FakeResponse(
            json_data={"choices": [{"message": {"content": "generated text"}}]}
        )

    def stream(self, method, path, headers=None, json=None):
        self.__class__.last_stream_request = {
            "method": method,
            "path": path,
            "headers": headers,
            "json": json,
        }
        response = _FakeStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"Hel"}}]}',
                'data: {"choices":[{"delta":{"content":"lo"}}]}',
                "data: [DONE]",
            ]
        )
        return _FakeStreamContext([], response)


def test_call_grok_returns_generated_text(monkeypatch):
    async def run():
        monkeypatch.setenv("GROQ_API_KEY", "secret")
        monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
        monkeypatch.setattr(grok_client.httpx, "AsyncClient", _FakeAsyncClient)

        result = await grok_client.call_grok([{"role": "user", "content": "Hello"}], max_tokens=42)

        assert result == "generated text"
        assert _FakeAsyncClient.last_request["json"]["model"] == "openai/gpt-oss-120b"
        assert _FakeAsyncClient.last_request["json"]["max_completion_tokens"] == 42
        assert _FakeAsyncClient.last_request["json"]["stream"] is False
        assert _FakeAsyncClient.last_request["json"]["reasoning_effort"] == "medium"
        assert _FakeAsyncClient.last_request["json"]["include_reasoning"] is False

    anyio.run(run)


def test_stream_grok_yields_chunks(monkeypatch):
    async def run():
        monkeypatch.setenv("GROQ_API_KEY", "secret")
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        monkeypatch.setattr(grok_client.httpx, "AsyncClient", _FakeAsyncClient)

        chunks = []
        async for chunk in grok_client.stream_grok(
            [{"role": "user", "content": "Hello"}], max_tokens=42
        ):
            chunks.append(chunk)

        assert chunks == ["Hel", "lo"]
        assert _FakeAsyncClient.last_stream_request["json"]["stream"] is True
        assert _FakeAsyncClient.last_stream_request["json"]["model"] == "openai/gpt-oss-120b"
        assert _FakeAsyncClient.last_stream_request["json"]["max_completion_tokens"] == 42

    anyio.run(run)


def test_call_grok_raises_exception_for_http_error(monkeypatch):
    class ErrorClient(_FakeAsyncClient):
        async def post(self, path, headers=None, json=None):
            request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
            response = httpx.Response(503, text="upstream unavailable", request=request)
            raise httpx.HTTPStatusError("boom", request=request, response=response)

    async def run():
        monkeypatch.setenv("GROQ_API_KEY", "secret")
        monkeypatch.setattr(grok_client.httpx, "AsyncClient", ErrorClient)

        with pytest.raises(grok_client.GrokApiException) as exc_info:
            await grok_client.call_grok([{"role": "user", "content": "Hello"}], max_tokens=42)

        assert exc_info.value.status_code == 503
        assert "upstream unavailable" in exc_info.value.message

    anyio.run(run)
