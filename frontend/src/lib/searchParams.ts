/**
 * Разбор/сборка query-параметров экранов. Выбор пользователя (тикеры,
 * период, режим графика) живёт в URL, а не в `useState`/`localStorage` —
 * ссылка на сравнение копируется как есть, а F5 ничего не теряет.
 * Значение по умолчанию в URL не дописывается (страница сама подставляет
 * его на лету, если параметра нет или он невалиден).
 */

export type ChartScale = "intraday" | "daily";
export type ChartMode = "absolute" | "percent";
export type HistoryPeriod = "1m" | "6m" | "1y" | "all";

const HISTORY_PERIODS: readonly HistoryPeriod[] = ["1m", "6m", "1y", "all"];

export function parseScale(value: string | null): ChartScale {
  return value === "daily" ? "daily" : "intraday";
}

export function parseMode(value: string | null): ChartMode {
  return value === "absolute" ? "absolute" : "percent";
}

export function parsePeriod(value: string | null): HistoryPeriod {
  return (HISTORY_PERIODS as readonly string[]).includes(value ?? "")
    ? (value as HistoryPeriod)
    : "1y";
}

/** `?secids=SBER,LKOH` → `["SBER", "LKOH"]`, без пустых элементов и дублей. */
export function parseTickerList(value: string | null): string[] {
  if (!value) {
    return [];
  }
  const seen = new Set<string>();
  for (const raw of value.split(",")) {
    const ticker = raw.trim().toUpperCase();
    if (ticker !== "") {
      seen.add(ticker);
    }
  }
  return [...seen];
}

export function tickerListToParam(tickers: readonly string[]): string | null {
  return tickers.length > 0 ? tickers.join(",") : null;
}

/** Обновить один параметр, не потеряв остальные (`null` — удалить параметр). */
export function withParam(
  params: URLSearchParams,
  key: string,
  value: string | null,
): URLSearchParams {
  const next = new URLSearchParams(params);
  if (value === null) {
    next.delete(key);
  } else {
    next.set(key, value);
  }
  return next;
}

/** Начало периода для `history` по выбору пользователя; `"all"` — без `from` (весь период). */
export function periodToFromDate(period: HistoryPeriod, now: Date = new Date()): string | undefined {
  if (period === "all") {
    return undefined;
  }
  const from = new Date(now);
  if (period === "1m") {
    from.setUTCMonth(from.getUTCMonth() - 1);
  } else if (period === "6m") {
    from.setUTCMonth(from.getUTCMonth() - 6);
  } else {
    from.setUTCFullYear(from.getUTCFullYear() - 1);
  }
  return from.toISOString().slice(0, 10);
}
