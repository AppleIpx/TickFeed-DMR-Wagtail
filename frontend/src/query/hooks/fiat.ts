import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { FiatRate, FiatRatePoint } from "@/api/types";
import type { QueryOptions } from "@/query/hooks/crypto";
import type { HistoryRange } from "@/query/keys";
import { queryKeys } from "@/query/keys";

export function useFiatRates(options: QueryOptions = {}) {
  return useQuery<FiatRate[]>({
    queryKey: queryKeys.fiat.rates(),
    queryFn: async () => unwrap(await api.GET("/api/fiat/rates/")),
    enabled: options.enabled ?? true,
  });
}

export function useFiatHistory(
  isoCode: string | undefined,
  range: HistoryRange = {},
  options: QueryOptions = {},
) {
  return useQuery<FiatRatePoint[]>({
    queryKey: queryKeys.fiat.history(isoCode, range),
    queryFn: async () => {
      if (isoCode === undefined) {
        throw new Error("Запрос без ISO-кода — хук должен быть выключен");
      }
      return unwrap(
        await api.GET("/api/fiat/rates/{iso_code}/history", {
          params: {
            path: { iso_code: isoCode },
            query: { from: range.from, to: range.to },
          },
        }),
      );
    },
    enabled: isoCode !== undefined && (options.enabled ?? true),
  });
}
