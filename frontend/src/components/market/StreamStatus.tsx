import { AlertTriangle, CircleAlert, Loader2, Radio, RadioTower } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { StreamFatalError, StreamStatus as Status } from "@/api/stream";
import type { StreamWarning } from "@/api/types";

const STATUS_LABEL: Record<Status, string> = {
  connecting: "подключение…",
  open: "поток открыт",
  reconnecting: "переподключение…",
  closed: "закрыт",
};

function StatusIcon({ status }: { status: Status }) {
  switch (status) {
    case "open":
      return <Radio className="size-3.5" aria-hidden />;
    case "connecting":
    case "reconnecting":
      return <Loader2 className="size-3.5 animate-spin" aria-hidden />;
    case "closed":
      return <RadioTower className="size-3.5" aria-hidden />;
  }
}

export interface StreamStatusProps {
  status: Status;
  lastHeartbeatAt: string | null;
  warning: StreamWarning | null;
  fatal: StreamFatalError | null;
}

/**
 * Состояние `EventSource` + `warning`/`fatal` из конверта событий.
 * `fatal` — как правило 404 (ни один тикер не найден): `EventSource` на
 * нём сам перестаёт переподключаться, это штатное поведение, не сбой сети.
 */
export function StreamStatus({ status, lastHeartbeatAt, warning, fatal }: StreamStatusProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <Badge
          variant="outline"
          className={cn(
            "gap-1",
            status === "open" && "border-realtime/40 bg-realtime/10 text-realtime",
            (status === "connecting" || status === "reconnecting") &&
              "border-stale/40 bg-stale/10 text-stale",
            status === "closed" && "border-destructive/40 bg-destructive/10 text-destructive",
          )}
        >
          <StatusIcon status={status} />
          {STATUS_LABEL[status]}
        </Badge>
        {status === "open" && lastHeartbeatAt && (
          <span className="text-xs text-muted-foreground">heartbeat: {lastHeartbeatAt}</span>
        )}
      </div>
      {warning && (
        <p className="flex items-start gap-1.5 text-xs text-stale">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {warning.detail} (не найдены: {warning.unknown.join(", ")})
        </p>
      )}
      {fatal && (
        <p className="flex items-start gap-1.5 text-xs text-destructive">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {fatal.message}
        </p>
      )}
    </div>
  );
}
