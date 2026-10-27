import { useMemo, useState } from "react";
import { Check, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { CHART_SERIES_TOKENS } from "@/components/market/chartTheme";
import { cn } from "@/lib/utils";
import type { StockAsset } from "@/api/types";

const MAX_VISIBLE_ITEMS = 50;
const NO_TRADES_HINT = "Лента сделок для этой бумаги не ведётся";

export interface TickerPickerProps {
  assets: readonly StockAsset[];
  selected: readonly string[];
  onChange: (secids: string[]) => void;
  /** Столько цветов в палитре `PriceChart` (`--chart-1`…`--chart-6`). */
  max?: number;
}

/** Мультивыбор бумаг для `/stocks`: чипы выбранных + Popover с поиском. */
export function TickerPicker({ assets, selected, onChange, max = 6 }: TickerPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const matches = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (normalized === "") {
      return assets;
    }
    return assets.filter(
      (asset) =>
        asset.symbol.toLowerCase().includes(normalized) ||
        asset.display_name.toLowerCase().includes(normalized),
    );
  }, [assets, query]);

  const visible = matches.slice(0, MAX_VISIBLE_ITEMS);
  const limitReached = selected.length >= max;

  const toggle = (symbol: string) => {
    onChange(
      selected.includes(symbol) ? selected.filter((item) => item !== symbol) : [...selected, symbol],
    );
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) {
      setQuery("");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {selected.map((symbol, index) => {
        const colorToken = CHART_SERIES_TOKENS[index % CHART_SERIES_TOKENS.length];
        const asset = assets.find((item) => item.symbol === symbol);
        return (
          <span
            key={symbol}
            title={asset && !asset.track_trades ? NO_TRADES_HINT : undefined}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-ring bg-accent pr-1 pl-2.5 text-sm font-semibold text-accent-foreground shadow-sm"
          >
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: `var(--${colorToken})` }}
            />
            {symbol}
            <button
              type="button"
              aria-label={`Убрать ${symbol}`}
              onClick={() => toggle(symbol)}
              className="rounded-sm p-1 text-muted-foreground hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              <X className="size-3.5" />
            </button>
          </span>
        );
      })}
      <Popover open={open} onOpenChange={handleOpenChange}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" disabled={limitReached}>
            <Plus className="size-4" />
            Добавить
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[min(20rem,calc(100vw-2rem))] p-0">
          <Command shouldFilter={false}>
            <CommandInput
              value={query}
              onValueChange={setQuery}
              placeholder="Тикер или название..."
            />
            <CommandList>
              <CommandEmpty>Ничего не найдено.</CommandEmpty>
              <CommandGroup>
                {visible.map((asset) => {
                  const selectedIndex = selected.indexOf(asset.symbol);
                  const isSelected = selectedIndex !== -1;
                  const colorToken = CHART_SERIES_TOKENS[selectedIndex % CHART_SERIES_TOKENS.length];
                  return (
                    <CommandItem
                      key={asset.symbol}
                      value={asset.symbol}
                      disabled={!isSelected && limitReached}
                      title={asset.track_trades ? undefined : NO_TRADES_HINT}
                      onSelect={() => toggle(asset.symbol)}
                    >
                      <Check className={cn("size-4", isSelected ? "opacity-100" : "opacity-0")} />
                      {isSelected && (
                        <span
                          aria-hidden
                          className="size-2 shrink-0 rounded-full"
                          style={{ backgroundColor: `var(--${colorToken})` }}
                        />
                      )}
                      <span className="font-medium">{asset.symbol}</span>
                      <span className="truncate text-muted-foreground">{asset.display_name}</span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
              {matches.length > visible.length && (
                <p className="px-3 py-2 text-xs text-muted-foreground">
                  Показано {visible.length} из {matches.length} — уточните запрос.
                </p>
              )}
            </CommandList>
            <p className="border-t px-3 py-2 text-xs text-muted-foreground">
              Выбрано {selected.length} из {max}
            </p>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
