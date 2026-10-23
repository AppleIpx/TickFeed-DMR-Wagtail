from dmr.streaming.sse import SSEvent

from tickfeeddmr.ai.api.schemas.chat import (
    ChatDoneOut,
    ChatErrorOut,
    ChatEventOut,
    ChatTextDeltaOut,
    ChatToolCallOut,
)
from tickfeeddmr.ai.services.chat.events import (
    ChatEvent,
    DoneEvent,
    ErrorEvent,
    TextDeltaEvent,
    ToolCallEvent,
)

EVENT_NAMES: dict[type, str] = {
    ChatTextDeltaOut: "text_delta",
    ChatToolCallOut: "tool_call",
    ChatDoneOut: "done",
    ChatErrorOut: "error",
}


def to_out(event: ChatEvent) -> ChatEventOut | None:
    """Доменное событие → событие API; служебные (сводка) пропускаются."""
    match event:
        case TextDeltaEvent():
            return ChatTextDeltaOut(text=event.text)
        case ToolCallEvent():
            return ChatToolCallOut(name=event.name, label=event.label)
        case DoneEvent():
            return ChatDoneOut(model=event.model)
        case ErrorEvent():
            return ChatErrorOut(message=event.message)
    return None


def to_sse(out: ChatEventOut) -> SSEvent[ChatEventOut]:
    """Обернуть событие в SSE-конверт с именем; `id` не выставляется."""
    return SSEvent(out, event=EVENT_NAMES[type(out)])
