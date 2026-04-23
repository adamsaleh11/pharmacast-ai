import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

import shared.grok_client as grok_client
from apps.llm_service.app.schemas.chat import ChatRequest
from apps.llm_service.app.services.chat_policy import build_chat_messages
from shared.validators import validate_no_patient_data


router = APIRouter(prefix="/chat", tags=["llm"])
logger = logging.getLogger(__name__)


@router.post("")
async def chat(request: ChatRequest):
    validate_no_patient_data({"messages": request.messages, "system": request.system_prompt})
    messages = build_chat_messages(request.system_prompt, request.messages)

    async def event_stream():
        emitted_text = []
        try:
            with grok_client.feature_context("chat"):
                async for token in grok_client.stream_grok(messages, max_tokens=2000):
                    emitted_text.append(token)
                    yield f"data: {json.dumps({'token': token})}\n\n"

            total_tokens = max(1, len("".join(emitted_text)) // 4)
            yield f"data: {json.dumps({'done': True, 'total_tokens': total_tokens})}\n\n"
        except grok_client.GrokApiException as exc:
            logger.warning(
                "llm_chat_stream_error",
                extra={
                    "status_code": exc.status_code,
                    "message_count": len(request.messages),
                    "system_chars": len(request.system_prompt),
                },
            )
            yield f"data: {json.dumps({'error': 'LLM_UNAVAILABLE', 'message': 'Try again in a moment'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
