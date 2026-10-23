import { MessageCircle, X } from "lucide-react";
import { useState } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { isLimitExhausted, remainingPercent } from "@/lib/aiUsage";
import { useAiStatus } from "@/query/hooks/ai";
import { useChat } from "@/query/hooks/useChat";

const DEFAULT_LIMITS = { maxMessages: 1, maxMessageChars: 1 };

export function ChatWidget() {
  const status = useAiStatus();
  const [open, setOpen] = useState(false);
  const chat = useChat(
    status.data
      ? { maxMessages: status.data.max_messages, maxMessageChars: status.data.max_message_chars }
      : DEFAULT_LIMITS,
  );

  if (!status.data?.enabled) {
    return null;
  }

  const { model, usage, max_message_chars: maxChars } = status.data;
  const exhausted = isLimitExhausted(usage);

  return (
    <>
      <Card
        className={cn(
          "fixed bottom-24 right-6 z-50 h-[min(600px,calc(100vh-8rem))] w-[min(420px,calc(100vw-3rem))] flex-col gap-0 py-0",
          open ? "flex" : "hidden",
        )}
      >
        <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium">ИИ-аналитик</span>
              {model !== null && <Badge variant="secondary">{model}</Badge>}
            </div>
            {usage !== null && (
              <p className="text-xs text-muted-foreground">
                осталось ~{remainingPercent(usage)}% на сегодня
              </p>
            )}
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={chat.reset}>
            Новый диалог
          </Button>
        </div>
        <ChatMessageList entries={chat.entries} activeTool={chat.activeTool} />
        {exhausted && (
          <div className="px-3 pb-3">
            <Alert>
              <AlertDescription>
                Лимит на сегодня исчерпан, сброс в 00:00 МСК.
              </AlertDescription>
            </Alert>
          </div>
        )}
        <ChatInput
          maxChars={maxChars}
          isStreaming={chat.isStreaming}
          disabled={exhausted}
          onSend={chat.send}
          onStop={chat.stop}
        />
      </Card>
      <Button
        type="button"
        size="icon"
        className="fixed bottom-6 right-6 z-50 size-12 rounded-full shadow-lg"
        aria-label={open ? "Закрыть чат" : "Открыть чат"}
        onClick={() => {
          setOpen((previous) => !previous);
        }}
      >
        {open ? <X /> : <MessageCircle />}
      </Button>
    </>
  );
}
