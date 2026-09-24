import { Check } from "lucide-react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CHART_SERIES_TOKENS } from "@/components/market/chartTheme";
import { cn } from "@/lib/utils";
import type { StockAsset } from "@/api/types";

export interface TickerPickerProps {
  assets: readonly StockAsset[];
  selected: readonly string[];
  onChange: (secids: string[]) => void;
  /** Столько цветов в палитре `PriceChart` (`--chart-1`…`--chart-6`). */
  max?: number;
}

/**
 * Мультивыбор бумаг для `/stocks`. Чипы сверх `max` дизейблятся, а не
 * молча срезаются в `onValueChange` — иначе `ToggleGroup` (полностью
 * управляемый через `value`) на долю секунды показал бы выбор, который
 * родитель тут же откатит, не приняв.
 *
 * Выбранный чип получает кружок цвета своей линии на `PriceChart` (тот
 * же порядок токенов `--chart-1`…`--chart-6`, что и `chartSeriesColor`)
 * и усиленную заливку вместо едва заметного `bg-accent` из `Toggle` по
 * умолчанию — иначе клик по чипу ничем не выдаёт, какая линия на
 * графике ему соответствует, и результат клика не считывается сразу.
 */
export function TickerPicker({ assets, selected, onChange, max = 6 }: TickerPickerProps) {
  return (
    <ToggleGroup
      type="multiple"
      value={selected as string[]}
      onValueChange={onChange}
      variant="outline"
      size="sm"
      className="flex-wrap justify-start gap-1.5"
      spacing={1}
    >
      {assets.map((asset) => {
        const selectedIndex = selected.indexOf(asset.symbol);
        const isSelected = selectedIndex !== -1;
        const colorToken = CHART_SERIES_TOKENS[selectedIndex % CHART_SERIES_TOKENS.length];
        return (
          <ToggleGroupItem
            key={asset.symbol}
            value={asset.symbol}
            disabled={!isSelected && selected.length >= max}
            aria-label={asset.display_name}
            title={asset.track_trades ? undefined : "Лента сделок для этой бумаги не ведётся"}
            className={cn(
              "gap-1.5 border",
              isSelected &&
                "border-ring bg-accent font-semibold text-accent-foreground shadow-sm data-[state=on]:bg-accent",
            )}
          >
            {isSelected && (
              <span
                aria-hidden
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: `var(--${colorToken})` }}
              />
            )}
            {isSelected && <Check className="size-3.5" />}
            {asset.symbol}
          </ToggleGroupItem>
        );
      })}
    </ToggleGroup>
  );
}
