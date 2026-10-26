import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { AiStatus } from "@/api/types";
import { queryKeys } from "@/query/keys";

const STATUS_STALE_MS = 5 * 60_000;

export function useAiStatus() {
  return useQuery<AiStatus>({
    queryKey: queryKeys.ai.status(),
    queryFn: async () => unwrap(await api.GET("/api/ai/status")),
    retry: false,
    staleTime: STATUS_STALE_MS,
  });
}
