export interface HistoryRange {
  from?: string;
  to?: string;
}

export interface TradesPage {
  limit?: number;
  cursor?: string;
}

const crypto = {
  all: ["crypto"] as const,
  assets: () => [...crypto.all, "assets"] as const,
  current: (symbol: string | undefined) => [...crypto.all, "current", symbol] as const,
  trades: (symbol: string | undefined, page: TradesPage) =>
    [...crypto.all, "trades", symbol, page] as const,
  intraday: (symbol: string | undefined) => [...crypto.all, "intraday", symbol] as const,
  history: (symbol: string | undefined, range: HistoryRange) =>
    [...crypto.all, "history", symbol, range] as const,
};

const stocks = {
  all: ["stocks"] as const,
  assets: () => [...stocks.all, "assets"] as const,
  current: (secid: string | undefined) => [...stocks.all, "current", secid] as const,
  trades: (secid: string | undefined, page: TradesPage) =>
    [...stocks.all, "trades", secid, page] as const,
  intraday: (secid: string | undefined) => [...stocks.all, "intraday", secid] as const,
  history: (secid: string | undefined, range: HistoryRange) =>
    [...stocks.all, "history", secid, range] as const,
};

const fiat = {
  all: ["fiat"] as const,
  rates: () => [...fiat.all, "rates"] as const,
  history: (isoCode: string | undefined, range: HistoryRange) =>
    [...fiat.all, "history", isoCode, range] as const,
};

export const queryKeys = { crypto, stocks, fiat };
