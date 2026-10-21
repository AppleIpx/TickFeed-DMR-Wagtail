import msgspec


class FnDelta(msgspec.Struct):
    name: str | None = None
    arguments: str | None = None


class ToolCallDelta(msgspec.Struct):
    index: int | None = None
    id: str | None = None
    function: FnDelta | None = None


class Delta(msgspec.Struct):
    content: str | None = None
    tool_calls: list[ToolCallDelta] | None = None


class Choice(msgspec.Struct):
    delta: Delta | None = None
    finish_reason: str | None = None


class Usage(msgspec.Struct):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class StreamError(msgspec.Struct):
    message: str = ""


class Chunk(msgspec.Struct):
    """Один фрагмент SSE-стрима `/chat/completions`."""

    choices: list[Choice] = []
    usage: Usage | None = None
    error: StreamError | None = None


class ToolCallAcc(msgspec.Struct):
    """Накопитель фрагментов одного вызова инструмента."""

    id: str = ""
    name: str = ""
    parts: list[str] = []
