import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
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
 */
export function TickerPicker({ assets, selected, onChange, max = 6 }: TickerPickerProps) {
  return (
    <ToggleGroup
      type="multiple"
      value={selected as string[]}
      onValueChange={onChange}
      variant="outline"
      size="sm"
      className="flex-wrap justify-start"
    >
      {assets.map((asset) => {
        const isSelected = selected.includes(asset.symbol);
        return (
          <ToggleGroupItem
            key={asset.symbol}
            value={asset.symbol}
            disabled={!isSelected && selected.length >= max}
            aria-label={asset.display_name}
            title={asset.track_trades ? undefined : "Лента сделок для этой бумаги не ведётся"}
          >
            {asset.symbol}
          </ToggleGroupItem>
        );
      })}
    </ToggleGroup>
  );
}
