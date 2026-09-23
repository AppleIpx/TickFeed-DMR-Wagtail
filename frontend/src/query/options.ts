import { queryOptions } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type {
  Intraday,
  StockAsset,
  StockCurrent,
  StockPricePoint,
  StockTradePage,
} from "@/api/types";
import type { HistoryRange, TradesPage } from "@/query/keys";
import { queryKeys } from "@/query/keys";

/**
 * `queryOptions`-фабрики для акций — единственное место, которое знает
 * запрос/ключ кэша для секции `/stocks`. Нужны, а не только обычные хуки,
 * потому что число сравниваемых бумаг переменное: `useQueries` (этап 10.4,
 * `hooks/stocks.ts::use*Many`) принимает массив таких опций, а вызывать
 * хук в цикле — нарушение правил хуков React. Одиночные `use*`-хуки
 * ниже построены на этих же фабриках, чтобы ключи кэша не разъехались
 * между двумя путями (выбор одной бумаги на будущих экранах против
 * сравнения нескольких на `/stocks`).
 */

function requireSecid(secid: string | undefined): string {
  if (secid === undefined) {
    throw new Error("Запрос без SECID — хук должен быть выключен");
  }
  return secid;
}

export function stockAssetsOptions() {
  return queryOptions<StockAsset[]>({
    queryKey: queryKeys.stocks.assets(),
    queryFn: async () => unwrap(await api.GET("/api/stocks/")),
  });
}

export function stockCurrentOptions(secid: string | undefined) {
  return queryOptions<StockCurrent>({
    queryKey: queryKeys.stocks.current(secid),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/stocks/{secid}/current", {
          params: { path: { secid: requireSecid(secid) } },
        }),
      ),
  });
}

export function stockTradesOptions(secid: string | undefined, page: TradesPage = {}) {
  return queryOptions<StockTradePage>({
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
  });
}

export function stockIntradayOptions(secid: string | undefined) {
  return queryOptions<Intraday>({
    queryKey: queryKeys.stocks.intraday(secid),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/stocks/{secid}/intraday", {
          params: { path: { secid: requireSecid(secid) } },
        }),
      ),
  });
}

export function stockHistoryOptions(secid: string | undefined, range: HistoryRange = {}) {
  return queryOptions<StockPricePoint[]>({
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
  });
}
