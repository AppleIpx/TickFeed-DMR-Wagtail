import Markdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Alert, AlertDescription } from "@/components/ui/alert";
import type { ChatEntry } from "@/query/hooks/chatState";
import { cn } from "@/lib/utils";

const MARKDOWN_COMPONENTS: Components = {
  a: ({ node: _node, ...props }) => (
    <a {...props} target="_blank" rel="noreferrer noopener" className="underline" />
  ),
  p: ({ node: _node, ...props }) => <p {...props} className="mb-2 last:mb-0" />,
  ul: ({ node: _node, ...props }) => <ul {...props} className="mb-2 list-disc pl-5" />,
  ol: ({ node: _node, ...props }) => <ol {...props} className="mb-2 list-decimal pl-5" />,
  table: ({ node: _node, ...props }) => (
    <div className="mb-2 overflow-x-auto">
      <table {...props} className="w-full border-collapse text-sm" />
    </div>
  ),
  th: ({ node: _node, ...props }) => (
    <th {...props} className="border border-border px-2 py-1 text-left text-sm font-medium" />
  ),
  td: ({ node: _node, ...props }) => (
    <td {...props} className="border border-border px-2 py-1 text-sm" />
  ),
  code: ({ node: _node, ...props }) => (
    <code {...props} className="rounded bg-background px-1" />
  ),
};

export interface ChatMessageProps {
  entry: ChatEntry;
}

export function ChatMessage({ entry }: ChatMessageProps) {
  if (entry.role === "error") {
    return (
      <Alert variant="destructive">
        <AlertDescription>{entry.content}</AlertDescription>
      </Alert>
    );
  }

  if (entry.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
          {entry.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className={cn("max-w-[92%] rounded-lg bg-muted px-3 py-2 text-sm")}>
        <Markdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
          {entry.content}
        </Markdown>
        {entry.status === "stopped" && (
          <p className="mt-1 text-xs text-muted-foreground">ответ прерван</p>
        )}
      </div>
    </div>
  );
}
