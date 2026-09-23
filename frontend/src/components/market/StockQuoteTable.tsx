import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { FreshnessBadge } from "@/components/market/FreshnessBadge";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useStockCurrentMany } from "@/query/hooks/stocks";

export interface StockQuoteTableProps {
  secids: readonly string[];
}

/** Изменение за день («взлёты/падения» из общего контекста), не только график. */
export function StockQuoteTable({ secids }: StockQuoteTableProps) {
  const results = useStockCurrentMany(secids);

  if (secids.length === 0) {
    return <p className="text-sm text-muted-foreground">Выберите бумаги для сравнения.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Бумага</TableHead>
          <TableHead className="text-right">Цена</TableHead>
          <TableHead className="text-right">За день</TableHead>
          <TableHead>Свежесть</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {secids.map((secid, index) => {
          const result = results[index];

          if (!result || result.isPending) {
            return (
              <TableRow key={secid}>
                <TableCell className="font-medium">{secid}</TableCell>
                <TableCell colSpan={3}>
                  <Skeleton className="h-4 w-full" />
                </TableCell>
              </TableRow>
            );
          }

          if (result.isError || !result.data) {
            return (
              <TableRow key={secid}>
                <TableCell className="font-medium">{secid}</TableCell>
                <TableCell colSpan={3} className="text-sm text-destructive">
                  Не удалось загрузить.
                </TableCell>
              </TableRow>
            );
          }

          const current = result.data;
          const changePercent = current.change_percent;
          const isUp = changePercent !== null && !changePercent.startsWith("-");

          return (
            <TableRow key={secid}>
              <TableCell className="font-medium">{secid}</TableCell>
              <TableCell className="text-right tabular">
                {current.last !== null ? formatPrice(current.last) : "—"}
              </TableCell>
              <TableCell
                className={cn(
                  "text-right tabular",
                  changePercent !== null && (isUp ? "text-buy" : "text-sell"),
                )}
              >
                {changePercent !== null ? `${isUp ? "+" : ""}${changePercent}%` : "—"}
              </TableCell>
              <TableCell>
                <FreshnessBadge freshness={current.freshness} />
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
