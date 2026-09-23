import type { LineData, UTCTimestamp } from "lightweight-charts";

import { decimalPrecision } from "@/lib/format";
import type {
  CryptoTradeEvent,
  FiatRatePoint,
  LinearPricePoint,
  PricePoint,
  StockPricePoint,
  StockTradeEvent,
} from "@/api/types";

/** ISO-строка → секундный `UTCTimestamp`, единственный формат времени в проекте. */
export function toUtcTimestamp(iso: string): UTCTimestamp {
  return (Date.parse(iso) / 1000) as UTCTimestamp;
}

function toLineData(iso: string, price: string): LineData {
  return { time: toUtcTimestamp(iso), value: Number(price) };
}

/** Точность цены для `priceFormat.precision` — по самой точной точке серии. */
export function seriesPrecision(prices: readonly string[]): number {
  let precision = 2;
  for (const price of prices) {
    precision = Math.max(precision, decimalPrecision(price));
  }
  return Math.min(precision, 8);
}

/** `intraday` (общая линейная схема, крипта и акции) → точки графика. */
export function linearPointsToSeries(points: readonly LinearPricePoint[]): LineData[] {
  return points.map((point) => toLineData(point.timestamp, point.price));
}

/**
 * `history` крипты (дневная свеча) → цена закрытия дня. Временная витрина
 * 10.3 (`App.tsx`) сравнивает только акции — крипто-график `history`
 * получит отдельный экран в 10.4; функция здесь, чтобы модуль оставался
 * одним местом со всеми адаптерами `intraday`/`history`/`fiat`, а не
 * заводилась заново при роутинге.
 */
export function cryptoHistoryToSeries(points: readonly PricePoint[]): LineData[] {
  return points.map((point) => toLineData(point.timestamp, point.close));
}

type StockPricePointClosed = StockPricePoint & { close: string };

function hasClose(point: StockPricePoint): point is StockPricePointClosed {
  return point.close !== null;
}

/** `history` акций — `close` не гарантирован (сессия могла не закрыться). */
export function stockHistoryToSeries(points: readonly StockPricePoint[]): LineData[] {
  return points.filter(hasClose).map((point) => toLineData(point.timestamp, point.close));
}

/** Исходные строки цены закрытия — для `seriesPrecision` вызывающей стороны. */
export function stockClosePrices(points: readonly StockPricePoint[]): string[] {
  return points.filter(hasClose).map((point) => point.close);
}

/**
 * История курса ЦБ — одна точка в сутки. `RateTable` в 10.3 использует
 * только сырые значения (`Sparkline`), не `PriceChart` — этап 9 сознательно
 * отказался от живого графика валют; функция про запас на случай, если
 * 10.4 всё же захочет полноразмерный график истории курса.
 */
export function fiatHistoryToSeries(points: readonly FiatRatePoint[]): LineData[] {
  return points.map((point) => toLineData(point.timestamp, point.rate));
}

/**
 * Живой тик SSE → точка для `series.update()`. Сводится к минуте так же,
 * как бэкенд агрегирует `intraday` (`TruncMinute`) — иначе живой хвост
 * графика не совпадёт с тем, что вернёт следующий REST-запрос.
 */
export function tradeEventToMinutePoint(event: CryptoTradeEvent | StockTradeEvent): LineData {
  const timestamp = toUtcTimestamp(event.timestamp);
  const minuteTimestamp = (Math.floor(timestamp / 60) * 60) as UTCTimestamp;
  return { time: minuteTimestamp, value: Number(event.price) };
}
