import asyncio
import contextlib
import contextvars
import json
import logging
from collections.abc import AsyncGenerator
from time import perf_counter
from typing import Any

import httpx

from shared.config.settings import cached_settings


logger = logging.getLogger(__name__)

BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
TEMPERATURE = 0.6
TOP_P = 0.95
REASONING_EFFORT = "medium"
INCLUDE_REASONING = False
MAX_CONCURRENT_CALLS = 10

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
_feature_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "grok_feature",
    default="unknown",
)


class GrokApiException(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


@contextlib.contextmanager
def feature_context(feature: str):
    token = _feature_context.set(feature)
    try:
        yield
    finally:
        _feature_context.reset(token)


def _model_name() -> str:
    settings = cached_settings()
    return settings.groq_model or DEFAULT_MODEL


def _api_key() -> str:
    settings = cached_settings()
    if not settings.groq_api_key:
        raise GrokApiException(503, "GROQ_API_KEY is not configured")
    return settings.groq_api_key


def _estimate_token_count(messages: list[dict[str, Any]]) -> int:
    character_count = 0
    for message in messages:
        if isinstance(message, dict):
            character_count += len(str(message.get("content", "")))
        else:
            character_count += len(str(message))
    return max(1, character_count // 4)


def _log_call(feature: str, token_count_in: int, duration_ms: float) -> None:
    logger.info(
        "grok_call",
        extra={
            "feature": feature,
            "token_count_in": token_count_in,
            "duration_ms": round(duration_ms, 2),
        },
    )


async def call_grok(messages: list[dict], max_tokens: int) -> str:
    feature = _feature_context.get()
    token_count_in = _estimate_token_count(messages)
    start = perf_counter()

    async with _semaphore:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
            try:
                response = await client.post(
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {_api_key()}"},
                    json={
                        "model": _model_name(),
                        "messages": messages,
                        "temperature": TEMPERATURE,
                        "top_p": TOP_P,
                        "reasoning_effort": REASONING_EFFORT,
                        "include_reasoning": INCLUDE_REASONING,
                        "max_completion_tokens": max_tokens,
                        "stream": False,
                        "stop": None,
                    },
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                message = exc.response.text or exc.response.reason_phrase or "Grok request failed"
                raise GrokApiException(exc.response.status_code, message) from exc
            except httpx.HTTPError as exc:
                raise GrokApiException(503, str(exc)) from exc
            finally:
                _log_call(feature, token_count_in, (perf_counter() - start) * 1000)

    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        return ""
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    return str(content)


async def stream_grok(messages: list[dict], max_tokens: int) -> AsyncGenerator[str, None]:
    feature = _feature_context.get()
    token_count_in = _estimate_token_count(messages)
    start = perf_counter()

    async with _semaphore:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
            try:
                async with client.stream(
                    "POST",
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {_api_key()}"},
                    json={
                        "model": _model_name(),
                        "messages": messages,
                        "temperature": TEMPERATURE,
                        "top_p": TOP_P,
                        "reasoning_effort": REASONING_EFFORT,
                        "include_reasoning": INCLUDE_REASONING,
                        "max_completion_tokens": max_tokens,
                        "stream": True,
                        "stop": None,
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        payload = line.removeprefix("data:").strip()
                        if payload == "[DONE]":
                            break
                        data = json.loads(payload)
                        choices = data.get("choices", []) if isinstance(data, dict) else []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
                        content = delta.get("content", "") if isinstance(delta, dict) else ""
                        if content:
                            yield str(content)
            except httpx.HTTPStatusError as exc:
                message = exc.response.text or exc.response.reason_phrase or "Grok request failed"
                raise GrokApiException(exc.response.status_code, message) from exc
            except httpx.HTTPError as exc:
                raise GrokApiException(503, str(exc)) from exc
            finally:
                _log_call(feature, token_count_in, (perf_counter() - start) * 1000)
