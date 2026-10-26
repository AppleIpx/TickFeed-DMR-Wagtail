export type ChatEntry =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      status: "streaming" | "done" | "stopped";
    }
  | { id: string; role: "error"; content: string };

export interface ChatState {
  entries: ChatEntry[];
  activeTool: string | null;
  isStreaming: boolean;
}

export type ChatAction =
  | { type: "userSent"; id: string; content: string }
  | { type: "assistantStarted"; id: string }
  | { type: "delta"; text: string }
  | { type: "toolCall"; label: string }
  | { type: "done" }
  | { type: "failed"; id: string; message: string }
  | { type: "stopped" }
  | { type: "reset" };

export const initialChatState: ChatState = {
  entries: [],
  activeTool: null,
  isStreaming: false,
};

function mapLastAssistant(
  entries: ChatEntry[],
  update: (entry: Extract<ChatEntry, { role: "assistant" }>) => ChatEntry,
): ChatEntry[] {
  const index = entries.findLastIndex(
    (entry) => entry.role === "assistant" && entry.status === "streaming",
  );
  if (index === -1) {
    return entries;
  }
  const target = entries[index] as Extract<ChatEntry, { role: "assistant" }>;
  return entries.map((entry, i) => (i === index ? update(target) : entry));
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "userSent":
      return {
        ...state,
        entries: [...state.entries, { id: action.id, role: "user", content: action.content }],
      };
    case "assistantStarted":
      return {
        entries: [
          ...state.entries,
          { id: action.id, role: "assistant", content: "", status: "streaming" },
        ],
        activeTool: null,
        isStreaming: true,
      };
    case "delta":
      return {
        ...state,
        activeTool: null,
        entries: mapLastAssistant(state.entries, (entry) => ({
          ...entry,
          content: entry.content + action.text,
        })),
      };
    case "toolCall":
      return { ...state, activeTool: action.label };
    case "done":
      return {
        entries: mapLastAssistant(state.entries, (entry) => ({ ...entry, status: "done" })),
        activeTool: null,
        isStreaming: false,
      };
    case "failed": {
      const settled = mapLastAssistant(state.entries, (entry) => ({
        ...entry,
        status: "stopped",
      })).filter((entry) => !(entry.role === "assistant" && entry.content === ""));
      return {
        entries: [...settled, { id: action.id, role: "error", content: action.message }],
        activeTool: null,
        isStreaming: false,
      };
    }
    case "stopped":
      return {
        entries: mapLastAssistant(state.entries, (entry) => ({ ...entry, status: "stopped" })),
        activeTool: null,
        isStreaming: false,
      };
    case "reset":
      return initialChatState;
  }
}
