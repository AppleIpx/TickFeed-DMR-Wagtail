import { useEffect, useRef } from "react";

import { ChatMessage } from "@/components/chat/ChatMessage";
import { ToolCallIndicator } from "@/components/chat/ToolCallIndicator";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatEntry } from "@/query/hooks/chatState";

const EXAMPLE_QUESTIONS = [
  "Как SBER вёл себя по кварталам за последний год?",
  "Что сейчас с BTCUSDT: тренд и волатильность?",
  "Как изменился курс доллара за месяц?",
];

export interface ChatMessageListProps {
  entries: ChatEntry[];
  activeTool: string | null;
}

export function ChatMessageList({ entries, activeTool }: ChatMessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [entries, activeTool]);

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-3 p-4">
        {entries.length === 0 && (
          <div className="text-sm text-muted-foreground">
            <p className="mb-2">Спросите про котировки, например:</p>
            <ul className="list-disc pl-5">
              {EXAMPLE_QUESTIONS.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          </div>
        )}
        {entries.map((entry) => (
          <ChatMessage key={entry.id} entry={entry} />
        ))}
        {activeTool !== null && <ToolCallIndicator label={activeTool} />}
        <div ref={endRef} />
      </div>
    </ScrollArea>
  );
}
