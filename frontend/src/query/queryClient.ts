import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/errors";

const MAX_RETRIES = 2;
const STALE_TIME_MS = 30_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE_TIME_MS,
      refetchOnWindowFocus: false,
      retry: (failureCount: number, error: Error) => {
        if (error instanceof ApiError && error.status < 500) {
          return false;
        }
        return failureCount < MAX_RETRIES;
      },
    },
  },
});
