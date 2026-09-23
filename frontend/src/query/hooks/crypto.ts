import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type {
  Asset,
  CryptoCurrent,
  CryptoTradePage,
  Intraday,
  PricePoint,
} from "@/api/types";
import type { HistoryRange, TradesPage } from "@/query/keys";
import { queryKeys } from "@/query/keys";

export interface QueryOptions {
  enabled?: boolean;
}

function requireSymbol(symbol: string | undefined): string {
  if (symbol === undefined) {
    throw new Error("Запрос без символа пары — хук должен быть выключен");
  }
  return symbol;
}

export function useCryptoAssets(options: QueryOptions = {}) {
  return useQuery<Asset[]>({
    queryKey: queryKeys.crypto.assets(),
    queryFn: async () => unwrap(await api.GET("/api/crypto/assets/")),
    enabled: options.enabled ?? true,
  });
}

export function useCryptoCurrent(symbol: string | undefined, options: QueryOptions = {}) {
  return useQuery<CryptoCurrent>({
    queryKey: queryKeys.crypto.current(symbol),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/crypto/assets/{symbol}/current", {
          params: { path: { symbol: requireSymbol(symbol) } },
        }),
      ),
    enabled: symbol !== undefined && (options.enabled ?? true),
  });
}

export function useCryptoTrades(
  symbol: string | undefined,
  page: TradesPage = {},
  options: QueryOptions = {},
) {
  return useQuery<CryptoTradePage>({
    queryKey: queryKeys.crypto.trades(symbol, page),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/crypto/assets/{symbol}/trades", {
          params: {
            path: { symbol: requireSymbol(symbol) },
            query: { cursor: page.cursor, limit: page.limit },
          },
        }),
      ),
    enabled: symbol !== undefined && (options.enabled ?? true),
  });
}

export function useCryptoIntraday(symbol: string | undefined, options: QueryOptions = {}) {
  return useQuery<Intraday>({
    queryKey: queryKeys.crypto.intraday(symbol),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/crypto/assets/{symbol}/intraday", {
          params: { path: { symbol: requireSymbol(symbol) } },
        }),
      ),
    enabled: symbol !== undefined && (options.enabled ?? true),
  });
}

export function useCryptoHistory(
  symbol: string | undefined,
  range: HistoryRange = {},
  options: QueryOptions = {},
) {
  return useQuery<PricePoint[]>({
    queryKey: queryKeys.crypto.history(symbol, range),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/crypto/assets/{symbol}/history", {
          params: {
            path: { symbol: requireSymbol(symbol) },
            query: { from: range.from, to: range.to },
          },
        }),
      ),
    enabled: symbol !== undefined && (options.enabled ?? true),
  });
}
