import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { HistoryPeriod } from "@/lib/searchParams";

const OPTIONS: ReadonlyArray<{ value: HistoryPeriod; label: string }> = [
  { value: "1m", label: "1М" },
  { value: "6m", label: "6М" },
  { value: "1y", label: "1Г" },
  { value: "all", label: "Всё" },
];

export interface PeriodToggleProps {
  value: HistoryPeriod;
  onChange: (period: HistoryPeriod) => void;
}

/** Период `history` — только для вкладки «История» (`intraday` периода не имеет). */
export function PeriodToggle({ value, onChange }: PeriodToggleProps) {
  return (
    <ToggleGroup
      type="single"
      value={value}
      onValueChange={(next) => {
        if (next) {
          onChange(next as HistoryPeriod);
        }
      }}
      variant="outline"
      size="sm"
    >
      {OPTIONS.map((option) => (
        <ToggleGroupItem key={option.value} value={option.value}>
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
