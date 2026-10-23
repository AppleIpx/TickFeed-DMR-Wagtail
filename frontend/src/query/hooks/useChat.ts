import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useReducer, useRef } from "react";

import { ApiError } from "@/api/errors";
import { streamChat } from "@/api/chat";
import type { ChatMessageIn } from "@/api/types";
import { chatReducer, initialChatState } from "@/query/hooks/chatState";
import { queryKeys } from "@/query/keys";

export interface ChatLimits {
  maxMessages: number;
  maxMessageChars: number;
}

const NETWORK_ERROR_MESSAGE = "Не удалось связаться с сервером";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function useChat({ maxMessages, maxMessageChars }: ChatLimits) {
  const queryClient = useQueryClient();
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const controllerRef = useRef<AbortController | null>(null);

  const refreshStatus = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.ai.status() });
  }, [queryClient]);

  const send = useCallback(
    (text: string) => {
      const content = text.trim();
      if (state.isStreaming || content === "" || content.length > maxMessageChars) {
        return;
      }

      const history: ChatMessageIn[] = state.entries
        .filter(
          (entry) =>
            entry.role === "user" || (entry.role === "assistant" && entry.status === "done"),
        )
        .map((entry) => ({ role: entry.role as ChatMessageIn["role"], content: entry.content }));
      history.push({ role: "user", content });
      const trimmed = history.slice(-maxMessages);
      while (trimmed.length > 0 && trimmed[0]?.role !== "user") {
        trimmed.shift();
      }

      dispatch({ type: "userSent", id: crypto.randomUUID(), content });
      dispatch({ type: "assistantStarted", id: crypto.randomUUID() });

      const controller = new AbortController();
      controllerRef.current = controller;

      streamChat(
        { messages: trimmed },
        {
          onTextDelta: (event) => {
            dispatch({ type: "delta", text: event.text });
          },
          onToolCall: (event) => {
            dispatch({ type: "toolCall", label: event.label });
          },
          onDone: () => {
            dispatch({ type: "done" });
            refreshStatus();
          },
          onError: (event) => {
            dispatch({ type: "failed", id: crypto.randomUUID(), message: event.message });
            refreshStatus();
          },
        },
        controller.signal,
      ).catch((error: unknown) => {
        if (isAbortError(error)) {
          dispatch({ type: "stopped" });
        } else if (error instanceof ApiError) {
          dispatch({ type: "failed", id: crypto.randomUUID(), message: error.message });
        } else {
          dispatch({ type: "failed", id: crypto.randomUUID(), message: NETWORK_ERROR_MESSAGE });
        }
        refreshStatus();
      });
    },
    [state.entries, state.isStreaming, maxMessages, maxMessageChars, refreshStatus],
  );

  const stop = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    controllerRef.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  return {
    entries: state.entries,
    activeTool: state.activeTool,
    isStreaming: state.isStreaming,
    send,
    stop,
    reset,
  };
}
