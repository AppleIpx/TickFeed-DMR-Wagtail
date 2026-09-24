import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";

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
import { cn } from "@/lib/utils";

export interface AssetComboboxItem {
  symbol: string;
  display_name: string;
}

export interface AssetComboboxProps {
  items: readonly AssetComboboxItem[];
  value: string | undefined;
  onChange: (symbol: string) => void;
  placeholder?: string;
  className?: string;
}

/**
 * Выпадающий список с поиском по тикеру/названию — обычный `Select` не
 * фильтрует опции текстом, а список бумаг/пар наполняется через админку и
 * рассчитан на десятки записей.
 */
export function AssetCombobox({
  items,
  value,
  onChange,
  placeholder = "Выберите бумагу",
  className,
}: AssetComboboxProps) {
  const [open, setOpen] = useState(false);
  const selected = items.find((item) => item.symbol === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("w-44 justify-between font-normal", className)}
        >
          <span className="truncate">{selected ? selected.symbol : placeholder}</span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0">
        <Command>
          <CommandInput placeholder="Тикер или название..." />
          <CommandList>
            <CommandEmpty>Ничего не найдено.</CommandEmpty>
            <CommandGroup>
              {items.map((item) => (
                <CommandItem
                  key={item.symbol}
                  value={`${item.symbol} ${item.display_name}`}
                  onSelect={() => {
                    onChange(item.symbol);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn("size-4", item.symbol === value ? "opacity-100" : "opacity-0")}
                  />
                  <span className="font-medium">{item.symbol}</span>
                  <span className="truncate text-muted-foreground">{item.display_name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
