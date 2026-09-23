import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline } from "@/components/market/Sparkline";
import { formatMoscowDate, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useFiatHistory } from "@/query/hooks/fiat";
import type { FiatRate } from "@/api/types";

const SPARKLINE_WINDOW_DAYS = 30;

function sparklineFrom(): string {
  const from = new Date();
  from.setUTCDate(from.getUTCDate() - SPARKLINE_WINDOW_DAYS);
  return from.toISOString().slice(0, 10);
}

function RateSparklineCell({ isoCode }: { isoCode: string }) {
  const history = useFiatHistory(isoCode, { from: sparklineFrom() });

  if (history.isPending) {
    return <Skeleton className="h-7 w-24" />;
  }
  if (history.isError || !history.data) {
    return null;
  }
  return <Sparkline values={history.data.map((point) => Number(point.rate))} />;
}

export interface RateTableProps {
  rates: readonly FiatRate[];
  /** Выбранный код — подсвечивает строку (экран `/fiat` показывает её график). */
  selected?: string;
  onSelect?: (isoCode: string) => void;
}

/** Таблица курсов ЦБ РФ — одна точка в сутки, живого графика по решению
 *  этапа 9 нет, здесь только спарклайн последних 30 дней. */
export function RateTable({ rates, selected, onSelect }: RateTableProps) {
  if (rates.length === 0) {
    return <p className="text-sm text-muted-foreground">Список валют пуст.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Код</TableHead>
          <TableHead>Валюта</TableHead>
          <TableHead className="text-right">Курс, ₽</TableHead>
          <TableHead>Вступил в силу</TableHead>
          <TableHead>Динамика, 30 дн.</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rates.map((rate) => (
          <TableRow
            key={rate.iso_code}
            onClick={onSelect ? () => onSelect(rate.iso_code) : undefined}
            className={cn(
              onSelect && "cursor-pointer",
              selected === rate.iso_code && "bg-accent",
            )}
          >
            <TableCell className="font-medium tabular">{rate.iso_code}</TableCell>
            <TableCell>{rate.asset.display_name}</TableCell>
            <TableCell className="text-right tabular">{formatPrice(rate.rate)}</TableCell>
            <TableCell className="text-muted-foreground">
              {formatMoscowDate(rate.effective_date)}
            </TableCell>
            <TableCell>
              <RateSparklineCell isoCode={rate.iso_code} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
