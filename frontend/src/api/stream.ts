import { apiBaseUrl } from "@/api/client";
import type {
  CryptoStreamEvent,
  Heartbeat,
  StockStreamEvent,
  StreamWarning,
} from "@/api/types";

const EVENT_SOURCE_CLOSED = 2;

export interface EventSourceLike {
  readonly readyState: number;
  addEventListener(type: string, listener: (event: Event) => void): void;
  close(): void;
}

export type EventSourceFactory = (url: string) => EventSourceLike;

export interface StreamFatalError {
  message: string;
}

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed";

interface StreamEvent {
  kind: string;
}

type HandledKind = "trade" | "warning" | "heartbeat";

type AssertNever<T extends never> = T;

export type CryptoStreamFullyHandled = AssertNever<
  Exclude<CryptoStreamEvent, { kind: HandledKind }>
>;
export type StockStreamFullyHandled = AssertNever<
  Exclude<StockStreamEvent, { kind: HandledKind }>
>;

export interface TradeStreamHandlers<E extends StreamEvent> {
  onTrade: (event: Extract<E, { kind: "trade" }>) => void;
  onWarning: (event: StreamWarning) => void;
  onHeartbeat: (event: Heartbeat) => void;
  onOpen: () => void;
  onFatal: (error: StreamFatalError) => void;
  onReconnecting?: () => void;
}

export interface TradeStreamOptions<E extends StreamEvent> {
  path: string;
  paramName: string;
  tickers?: readonly string[];
  handlers: TradeStreamHandlers<E>;
  eventSourceFactory?: EventSourceFactory;
}

export interface TradeStream {
  close: () => void;
}

const defaultEventSourceFactory: EventSourceFactory = (url) =>
  new EventSource(url);

function buildUrl(path: string, paramName: string, tickers?: readonly string[]): string {
  const url = new URL(`${apiBaseUrl.replace(/\/+$/, "")}${path}`);
  if (tickers && tickers.length > 0) {
    url.searchParams.set(paramName, tickers.join(","));
  }
  return url.toString();
}

function parsePayload(event: Event, expectedKind: string): unknown {
  const raw = (event as MessageEvent<string>).data;
  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch (error: unknown) {
    console.warn(`SSE: не разобрано событие "${expectedKind}"`, error, raw);
    return undefined;
  }
  const kind = (payload as StreamEvent | null)?.kind;
  if (kind !== expectedKind) {
    console.warn(`SSE: событие "${expectedKind}" пришло с kind="${String(kind)}"`);
    return undefined;
  }
  return payload;
}

export function openTradeStream<E extends StreamEvent>({
  path,
  paramName,
  tickers,
  handlers,
  eventSourceFactory = defaultEventSourceFactory,
}: TradeStreamOptions<E>): TradeStream {
  const source = eventSourceFactory(buildUrl(path, paramName, tickers));
  let disposed = false;

  source.addEventListener("open", () => {
    if (disposed) {
      return;
    }
    handlers.onOpen();
  });

  source.addEventListener("error", () => {
    if (disposed) {
      return;
    }
    if (source.readyState === EVENT_SOURCE_CLOSED) {
      handlers.onFatal({
        message:
          "Поток закрыт сервером: вероятно, ни один из запрошенных тикеров не найден " +
          "(или их в запросе слишком много).",
      });
      return;
    }
    handlers.onReconnecting?.();
  });

  source.addEventListener("trade", (event) => {
    if (disposed) {
      return;
    }
    const payload = parsePayload(event, "trade");
    if (payload !== undefined) {
      handlers.onTrade(payload as Extract<E, { kind: "trade" }>);
    }
  });

  source.addEventListener("warning", (event) => {
    if (disposed) {
      return;
    }
    const payload = parsePayload(event, "warning");
    if (payload !== undefined) {
      handlers.onWarning(payload as StreamWarning);
    }
  });

  source.addEventListener("heartbeat", (event) => {
    if (disposed) {
      return;
    }
    const payload = parsePayload(event, "heartbeat");
    if (payload !== undefined) {
      handlers.onHeartbeat(payload as Heartbeat);
    }
  });

  return {
    close: () => {
      disposed = true;
      source.close();
    },
  };
}

type DomainStreamOptions<E extends StreamEvent> = Omit<
  TradeStreamOptions<E>,
  "path" | "paramName"
>;

export function openCryptoTradeStream<E extends StreamEvent>(
  options: DomainStreamOptions<E>,
): TradeStream {
  return openTradeStream({
    ...options,
    path: "/api/crypto/stream",
    paramName: "symbols",
  });
}

export function openStockTradeStream<E extends StreamEvent>(
  options: DomainStreamOptions<E>,
): TradeStream {
  return openTradeStream({
    ...options,
    path: "/api/stocks/stream",
    paramName: "secids",
  });
}
