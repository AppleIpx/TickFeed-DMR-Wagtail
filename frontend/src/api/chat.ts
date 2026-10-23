import type { EventSourceMessage } from "eventsource-parser";
import { createParser } from "eventsource-parser";

import { apiBaseUrl } from "@/api/client";
import { toApiError } from "@/api/errors";
import type {
  ChatDone,
  ChatError,
  ChatRequest,
  ChatStreamEvent,
  ChatTextDelta,
  ChatToolCall,
} from "@/api/types";

export interface ChatStreamHandlers {
  onTextDelta: (event: ChatTextDelta) => void;
  onToolCall: (event: ChatToolCall) => void;
  onDone: (event: ChatDone) => void;
  onError: (event: ChatError) => void;
}

type HandledKind = "text_delta" | "tool_call" | "done" | "error";

type AssertNever<T extends never> = T;

export type ChatStreamFullyHandled = AssertNever<
  Exclude<ChatStreamEvent, { kind: HandledKind }>
>;

const INTERRUPTED_MESSAGE = "Соединение прервано";

export async function streamChat(
  request: ChatRequest,
  handlers: ChatStreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${apiBaseUrl.replace(/\/+$/, "")}/api/ai/chat`, {
    method: "POST",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = undefined;
    }
    throw toApiError(res.status, body);
  }
  if (res.body === null) {
    throw toApiError(res.status, undefined);
  }

  let finished = false;

  const dispatch = (message: EventSourceMessage): void => {
    let payload: ChatStreamEvent;
    try {
      payload = JSON.parse(message.data) as ChatStreamEvent;
    } catch (error: unknown) {
      console.warn("SSE чата: не разобрано событие", error, message.data);
      return;
    }
    switch (payload.kind) {
      case "text_delta":
        handlers.onTextDelta(payload);
        break;
      case "tool_call":
        handlers.onToolCall(payload);
        break;
      case "done":
        finished = true;
        handlers.onDone(payload);
        break;
      case "error":
        finished = true;
        handlers.onError(payload);
        break;
      default: {
        const unhandled: never = payload;
        console.warn("SSE чата: неизвестный kind", unhandled);
      }
    }
  };

  const parser = createParser({ onEvent: dispatch });
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();

  for (;;) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    parser.feed(value);
  }

  if (!finished) {
    handlers.onError({ kind: "error", message: INTERRUPTED_MESSAGE });
  }
}
