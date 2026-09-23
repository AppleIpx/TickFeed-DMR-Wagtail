import { Clock3, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDelay, formatMoscowDateTime } from "@/lib/format";
import type { DataFreshness } from "@/api/types";

/**
 * Задержка данных — требование общего контекста проекта, не косметика:
 * у MOEX это ограничение бесплатного доступа к ISS (~15 минут), у ЦБ —
 * одна публикация в сутки. Показывать честно, не прятать в коде.
 */

const STALE_MULTIPLIER = 2;
const STALE_MIN_EXTRA_SECONDS = 60;

export interface FreshnessBadgeProps {
  freshness: DataFreshness;
  sourceHint?: string;
}

export function FreshnessBadge({ freshness, sourceHint }: FreshnessBadgeProps) {
  const ageSeconds = (Date.now() - Date.parse(freshness.timestamp)) / 1000;
  const isStale =
    !freshness.is_realtime &&
    ageSeconds > freshness.data_delay_seconds * STALE_MULTIPLIER + STALE_MIN_EXTRA_SECONDS;

  const label = freshness.is_realtime
    ? "в реальном времени"
    : `задержка ${formatDelay(freshness.data_delay_seconds)}`;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          className={
            freshness.is_realtime
              ? "border-realtime/40 bg-realtime/10 text-realtime"
              : isStale
                ? "border-stale/50 bg-stale/15 text-stale"
                : "border-muted-foreground/30 text-muted-foreground"
          }
        >
          {freshness.is_realtime ? (
            <Zap className="size-3" aria-hidden />
          ) : (
            <Clock3 className="size-3" aria-hidden />
          )}
          {label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        <p>Обновлено: {formatMoscowDateTime(freshness.timestamp)}</p>
        {sourceHint && <p className="text-muted-foreground">{sourceHint}</p>}
        {isStale && <p className="text-stale">Данные устарели сильнее заявленной задержки.</p>}
      </TooltipContent>
    </Tooltip>
  );
}
