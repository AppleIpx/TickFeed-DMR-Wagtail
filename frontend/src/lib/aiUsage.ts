import type { AiUsage } from "@/api/types";

export function isLimitExhausted(usage: AiUsage | null): boolean {
  if (usage === null) {
    return false;
  }
  return usage.requests >= usage.requests_limit || usage.tokens >= usage.tokens_limit;
}

export function remainingPercent(usage: AiUsage): number {
  const requests = 1 - usage.requests / usage.requests_limit;
  const tokens = 1 - usage.tokens / usage.tokens_limit;
  return Math.max(0, Math.round(Math.min(requests, tokens) * 100));
}
