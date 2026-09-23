import { useQueries, useQuery } from "@tanstack/react-query";

import {
  stockAssetsOptions,
  stockCurrentOptions,
  stockHistoryOptions,
  stockIntradayOptions,
  stockTradesOptions,
} from "@/query/options";
import type { QueryOptions } from "@/query/hooks/crypto";
import type { HistoryRange, TradesPage } from "@/query/keys";

export function useStockAssets(options: QueryOptions = {}) {
  return useQuery({ ...stockAssetsOptions(), enabled: options.enabled ?? true });
}

export function useStockCurrent(secid: string | undefined, options: QueryOptions = {}) {
  return useQuery({
    ...stockCurrentOptions(secid),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}

export function useStockTrades(
  secid: string | undefined,
  page: TradesPage = {},
  options: QueryOptions = {},
) {
  return useQuery({
    ...stockTradesOptions(secid, page),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}

export function useStockIntraday(secid: string | undefined, options: QueryOptions = {}) {
  return useQuery({
    ...stockIntradayOptions(secid),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}

export function useStockHistory(
  secid: string | undefined,
  range: HistoryRange = {},
  options: QueryOptions = {},
) {
  return useQuery({
    ...stockHistoryOptions(secid, range),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}

/**
 * Переменное число бумаг для сравнения на `/stocks` — вызывать `useQuery`
 * в цикле по секундам нельзя (нарушение правил хуков), `useQueries`
 * — штатный способ TanStack Query для ровно этого случая. Порядок
 * результатов совпадает с порядком `secids`.
 */
export function useStockIntradayMany(secids: readonly string[]) {
  return useQueries({ queries: secids.map((secid) => stockIntradayOptions(secid)) });
}

export function useStockHistoryMany(secids: readonly string[], range: HistoryRange = {}) {
  return useQueries({ queries: secids.map((secid) => stockHistoryOptions(secid, range)) });
}

export function useStockCurrentMany(secids: readonly string[]) {
  return useQueries({ queries: secids.map((secid) => stockCurrentOptions(secid)) });
}
