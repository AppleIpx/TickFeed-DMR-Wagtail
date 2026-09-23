import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { useEffect, useState } from "react";

import { formatMoscowTime, formatPrice, formatVolume } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CryptoTradeEvent, StockTradeEvent } from "@/api/types";

/** Общая строка ленты сделок — крипта и акции сводятся к ней адаптерами ниже. */
export interface TradeTapeRow {
  id: string;
  timestamp: string;
  price: string;
  amount: string;
  side: "buy" | "sell";
  note?: string;
}

type CryptoTradeLike = Pick<
  CryptoTradeEvent,
  "trade_id" | "timestamp" | "price" | "volume" | "side"
>;
type StockTradeLike = Pick<
  StockTradeEvent,
  "trade_id" | "timestamp" | "price" | "quantity" | "side" | "period"
>;

/** REST-страница (`CryptoTradeOut`) и SSE-событие (`CryptoTradeEventOut`)
 *  структурно совпадают в этих полях — общий адаптер для обоих. */
export function cryptoTradeToRow(event: CryptoTradeLike): TradeTapeRow {
  return {
    id: event.trade_id,
    timestamp: event.timestamp,
    price: event.price,
    amount: event.volume,
    side: event.side,
  };
}

export function stockTradeToRow(event: StockTradeLike): TradeTapeRow {
  return {
    id: String(event.trade_id),
    timestamp: event.timestamp,
    price: event.price,
    amount: String(event.quantity),
    side: event.side,
    note: event.period,
  };
}

const HIGHLIGHT_MS = 700;

function TradeRow({ row }: { row: TradeTapeRow }) {
  const [highlighted, setHighlighted] = useState(true);

  useEffect(() => {
    setHighlighted(true);
    const timer = window.setTimeout(() => setHighlighted(false), HIGHLIGHT_MS);
    return () => window.clearTimeout(timer);
    // Зависимость только от row.id: подсветка перезапускается на новую
    // строку, а не на любое изменение объекта row (в проекте нет ESLint —
    // exhaustive-deps здесь не проверяется автоматически).
  }, [row.id]);

  const isBuy = row.side === "buy";

  return (
    <li
      className={cn(
        "flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm transition-colors",
        highlighted && (isBuy ? "bg-buy/10" : "bg-sell/10"),
      )}
    >
      <span className="flex items-center gap-1.5 tabular text-muted-foreground">
        {formatMoscowTime(row.timestamp)}
        {row.note && <span className="text-xs opacity-70">· {row.note}</span>}
      </span>
      <span
        className={cn(
          "flex items-center gap-1 tabular font-medium",
          isBuy ? "text-buy" : "text-sell",
        )}
      >
        {isBuy ? (
          <ArrowUpRight className="size-3.5" aria-hidden />
        ) : (
          <ArrowDownRight className="size-3.5" aria-hidden />
        )}
        {formatPrice(row.price)}
      </span>
      <span className="tabular text-muted-foreground">{formatVolume(row.amount)}</span>
    </li>
  );
}

export interface TradeTapeProps {
  rows: readonly TradeTapeRow[];
  emptyLabel?: string;
}

/** Лента сделок со стороной — цвет и иконка одновременно (не только цвет). */
export function TradeTape({ rows, emptyLabel = "Сделок пока не было." }: TradeTapeProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }

  return (
    <ul className="flex max-h-80 flex-col gap-0.5 overflow-y-auto">
      {rows.map((row) => (
        <TradeRow key={row.id} row={row} />
      ))}
    </ul>
  );
}
