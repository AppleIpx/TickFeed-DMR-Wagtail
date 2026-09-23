import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type {
  Asset,
  Intraday,
  StockCurrent,
  StockPricePoint,
  StockTradePage,
} from "@/api/types";
import type { QueryOptions } from "@/query/hooks/crypto";
import type { HistoryRange, TradesPage } from "@/query/keys";
import { queryKeys } from "@/query/keys";

function requireSecid(secid: string | undefined): string {
  if (secid === undefined) {
    throw new Error("Запрос без SECID — хук должен быть выключен");
  }
  return secid;
}

export function useStockAssets(options: QueryOptions = {}) {
  return useQuery<Asset[]>({
    queryKey: queryKeys.stocks.assets(),
    queryFn: async () => unwrap(await api.GET("/api/stocks/")),
    enabled: options.enabled ?? true,
  });
}

export function useStockCurrent(secid: string | undefined, options: QueryOptions = {}) {
  return useQuery<StockCurrent>({
    queryKey: queryKeys.stocks.current(secid),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/stocks/{secid}/current", {
          params: { path: { secid: requireSecid(secid) } },
        }),
      ),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}

export function useStockTrades(
  secid: string | undefined,
  page: TradesPage = {},
  options: QueryOptions = {},
) {
  return useQuery<StockTradePage>({
    queryKey: queryKeys.stocks.trades(secid, page),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/stocks/{secid}/trades", {
          params: {
            path: { secid: requireSecid(secid) },
            query: { cursor: page.cursor, limit: page.limit },
          },
        }),
      ),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}

export function useStockIntraday(secid: string | undefined, options: QueryOptions = {}) {
  return useQuery<Intraday>({
    queryKey: queryKeys.stocks.intraday(secid),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/stocks/{secid}/intraday", {
          params: { path: { secid: requireSecid(secid) } },
        }),
      ),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}

export function useStockHistory(
  secid: string | undefined,
  range: HistoryRange = {},
  options: QueryOptions = {},
) {
  return useQuery<StockPricePoint[]>({
    queryKey: queryKeys.stocks.history(secid, range),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/stocks/{secid}/history", {
          params: {
            path: { secid: requireSecid(secid) },
            query: { from: range.from, to: range.to },
          },
        }),
      ),
    enabled: secid !== undefined && (options.enabled ?? true),
  });
}
