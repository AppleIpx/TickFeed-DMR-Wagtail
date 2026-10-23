import { Loader2 } from "lucide-react";

export interface ToolCallIndicatorProps {
  label: string;
}

export function ToolCallIndicator({ label }: ToolCallIndicatorProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      <span>{label}</span>
    </div>
  );
}
