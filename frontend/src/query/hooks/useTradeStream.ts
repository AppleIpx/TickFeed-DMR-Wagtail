import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  StreamFatalError,
  StreamStatus,
  TradeStream,
  TradeStreamHandlers,
} from "@/api/stream";
import { openCryptoTradeStream, openStockTradeStream } from "@/api/stream";
import type {
  CryptoStreamEvent,
  CryptoTradeEvent,
  Heartbeat,
  StockStreamEvent,
  StockTradeEvent,
  StreamWarning,
} from "@/api/types";
import { queryKeys } from "@/query/keys";

const DEFAULT_BUFFER_SIZE = 50;

export interface UseTradeStreamOptions<T = never> {
  tickers?: readonly string[];
  enabled?: boolean;
  bufferSize?: number;
  /**
   * Живой тик мимо React-состояния — для `PriceChart.series.update()`.
   * Вызывается синхронно на каждую сделку, помимо обычного накопления в
   * `trades`; не должен запускать перерисовку дерева самостоятельно.
   */
  onTrade?: (event: T) => void;
}

export interface TradeStreamState<T> {
  status: StreamStatus;
  trades: T[];
  warning: StreamWarning | null;
  lastHeartbeatAt: string | null;
  fatal: StreamFatalError | null;
}

type TradeOf<E> = Extract<E, { kind: "trade" }>;

type StreamOpener<E extends { kind: string }> = (options: {
  tickers?: readonly string[];
  handlers: TradeStreamHandlers<E>;
}) => TradeStream;

function useStream<E extends { kind: string }>(
  open: StreamOpener<E>,
  invalidateKey: readonly string[],
  {
    tickers,
    enabled = true,
    bufferSize = DEFAULT_BUFFER_SIZE,
    onTrade,
  }: UseTradeStreamOptions<TradeOf<E>>,
): TradeStreamState<TradeOf<E>> {
  const queryClient = useQueryClient();

  const [status, setStatus] = useState<StreamStatus>("closed");
  const [trades, setTrades] = useState<TradeOf<E>[]>([]);
  const [warning, setWarning] = useState<StreamWarning | null>(null);
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<string | null>(null);
  const [fatal, setFatal] = useState<StreamFatalError | null>(null);

  const tickersKey = tickers ? tickers.join(",") : "";
  const tickerList = useMemo(
    () => (tickersKey === "" ? undefined : tickersKey.split(",")),
    [tickersKey],
  );

  const bufferSizeRef = useRef(bufferSize);
  useEffect(() => {
    bufferSizeRef.current = bufferSize;
  }, [bufferSize]);

  // Актуальный колбэк в ref: не пересоздаём соединение при каждом рендере
  // компонента-подписчика (например, при смене периода графика).
  const onTradeRef = useRef(onTrade);
  useEffect(() => {
    onTradeRef.current = onTrade;
  }, [onTrade]);

  const pushTrade = useCallback((event: TradeOf<E>) => {
    onTradeRef.current?.(event);
    setTrades((previous) => [event, ...previous].slice(0, bufferSizeRef.current));
  }, []);

  useEffect(() => {
    if (!enabled) {
      setStatus("closed");
      return;
    }

    setTrades([]);
    setFatal(null);
    setLastHeartbeatAt(null);
    setStatus("connecting");
    const stream = open({
      tickers: tickerList,
      handlers: {
        onOpen: () => {
          setStatus("open");
          setWarning(null);
          setFatal(null);
          void queryClient.invalidateQueries({ queryKey: invalidateKey });
        },
        onTrade: pushTrade,
        onWarning: (event: StreamWarning) => {
          setWarning(event);
        },
        onHeartbeat: (event: Heartbeat) => {
          setLastHeartbeatAt(event.timestamp);
        },
        onReconnecting: () => {
          setStatus("reconnecting");
        },
        onFatal: (error: StreamFatalError) => {
          setStatus("closed");
          setFatal(error);
        },
      },
    });

    return () => {
      stream.close();
    };
  }, [enabled, tickerList, open, invalidateKey, pushTrade, queryClient]);

  return { status, trades, warning, lastHeartbeatAt, fatal };
}

export function useCryptoTradeStream(
  options: UseTradeStreamOptions<CryptoTradeEvent> = {},
): TradeStreamState<CryptoTradeEvent> {
  return useStream<CryptoStreamEvent>(
    openCryptoTradeStream,
    queryKeys.crypto.all,
    options,
  );
}

export function useStockTradeStream(
  options: UseTradeStreamOptions<StockTradeEvent> = {},
): TradeStreamState<StockTradeEvent> {
  return useStream<StockStreamEvent>(
    openStockTradeStream,
    queryKeys.stocks.all,
    options,
  );
}
