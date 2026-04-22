from apps.llm_service.app.schemas.common import AllowExtraModel


class ChatRequest(AllowExtraModel):
    system_prompt: str
    messages: list[dict[str, str]]
