import { Send, Square } from "lucide-react";
import { useState } from "react";
import type { KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export interface ChatInputProps {
  maxChars: number;
  isStreaming: boolean;
  disabled: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function ChatInput({ maxChars, isStreaming, disabled, onSend, onStop }: ChatInputProps) {
  const [draft, setDraft] = useState("");
  const canSend = !disabled && !isStreaming && draft.trim() !== "";

  const submit = () => {
    if (!canSend) {
      return;
    }
    onSend(draft);
    setDraft("");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex items-end gap-2 border-t p-3">
      <Textarea
        value={draft}
        maxLength={maxChars}
        disabled={disabled}
        placeholder="Задайте вопрос…"
        rows={2}
        className="min-h-0 resize-none"
        onChange={(event) => {
          setDraft(event.target.value);
        }}
        onKeyDown={handleKeyDown}
      />
      {isStreaming ? (
        <Button type="button" variant="outline" size="icon" aria-label="Остановить" onClick={onStop}>
          <Square />
        </Button>
      ) : (
        <Button type="button" size="icon" aria-label="Отправить" disabled={!canSend} onClick={submit}>
          <Send />
        </Button>
      )}
    </div>
  );
}
