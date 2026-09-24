import { useMemo, useRef } from "react";
import { useSearchParams } from "react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AssetCombobox } from "@/components/market/AssetCombobox";
import { FreshnessBadge } from "@/components/market/FreshnessBadge";
import { PeriodToggle } from "@/components/market/PeriodToggle";
import type { PriceChartHandle } from "@/components/market/PriceChart";
import { PriceChart } from "@/components/market/PriceChart";
import {
  cryptoHistoryToSeries,
  linearPointsToSeries,
  seriesPrecision,
  tradeEventToMinutePoint,
} from "@/components/market/series";
import { StreamStatus } from "@/components/market/StreamStatus";
import { TradeTape, cryptoTradeToRow, mergeTapeRows } from "@/components/market/TradeTape";
import {
  parsePeriod,
  parseScale,
  periodToFromDate,
  withParam,
} from "@/lib/searchParams";
import {
  useCryptoAssets,
  useCryptoCurrent,
  useCryptoHistory,
  useCryptoIntraday,
  useCryptoTrades,
} from "@/query/hooks/crypto";
import { useCryptoTradeStream } from "@/query/hooks/useTradeStream";

export function CryptoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const assets = useCryptoAssets();

  const activeAssets = useMemo(
    () => (assets.data ?? []).filter((asset) => asset.is_active),
    [assets.data],
  );
  const activeSymbols = useMemo(() => activeAssets.map((asset) => asset.symbol), [activeAssets]);
  const requestedSymbol = searchParams.get("symbol");
  const symbol =
    requestedSymbol && activeSymbols.includes(requestedSymbol)
      ? requestedSymbol
      : activeSymbols[0];

  const scale = parseScale(searchParams.get("view"));
  const period = parsePeriod(searchParams.get("period"));

  const current = useCryptoCurrent(symbol);
  const intraday = useCryptoIntraday(symbol, { enabled: scale === "intraday" });
  const history = useCryptoHistory(
    symbol,
    { from: periodToFromDate(period) },
    { enabled: scale === "daily" },
  );
  const trades = useCryptoTrades(symbol, { limit: 20 });

  const chartRef = useRef<PriceChartHandle>(null);
  const stream = useCryptoTradeStream({
    tickers: symbol ? [symbol] : undefined,
    enabled: symbol !== undefined,
    bufferSize: 20,
    onTrade: (event) => {
      // Живой тик — только на скользящий 24-часовой график: минутная
      // точка на дневной свече искажала бы её.
      if (scale === "intraday") {
        chartRef.current?.update(event.symbol, tradeEventToMinutePoint(event));
      }
    },
  });

  const series = useMemo(() => {
    if (!symbol) {
      return [];
    }
    if (scale === "intraday") {
      const points = intraday.data?.points ?? [];
      return [
        {
          id: symbol,
          label: symbol,
          points: linearPointsToSeries(points),
          precision: seriesPrecision(points.map((point) => point.price)),
        },
      ];
    }
    const points = history.data ?? [];
    return [
      {
        id: symbol,
        label: symbol,
        points: cryptoHistoryToSeries(points),
        precision: seriesPrecision(points.map((point) => point.close)),
      },
    ];
  }, [symbol, scale, intraday.data, history.data]);

  const tapeRows = useMemo(
    () =>
      mergeTapeRows(
        stream.trades.map((event) => cryptoTradeToRow(event)),
        (trades.data?.items ?? []).map((item) => cryptoTradeToRow(item)),
      ),
    [stream.trades, trades.data],
  );

  if (assets.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Не удалось загрузить список крипто-активов: {assets.error.message}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <AssetCombobox
          items={activeAssets}
          value={symbol}
          onChange={(value) => setSearchParams(withParam(searchParams, "symbol", value))}
          placeholder="Выберите пару"
        />
        {current.data && (
          <FreshnessBadge freshness={current.data.freshness} sourceHint="Binance WebSocket" />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          value={scale}
          onValueChange={(value) => setSearchParams(withParam(searchParams, "view", value))}
        >
          <TabsList>
            <TabsTrigger value="intraday">24 часа</TabsTrigger>
            <TabsTrigger value="daily">История</TabsTrigger>
          </TabsList>
        </Tabs>
        {scale === "daily" && (
          <PeriodToggle
            value={period}
            onChange={(next) => setSearchParams(withParam(searchParams, "period", next))}
          />
        )}
      </div>

      <PriceChart
        ref={chartRef}
        series={series}
        scale={scale}
        height={320}
        loading={scale === "intraday" ? intraday.isPending : history.isPending}
      />

      <StreamStatus
        status={stream.status}
        lastHeartbeatAt={stream.lastHeartbeatAt}
        warning={stream.warning}
        fatal={stream.fatal}
      />

      <TradeTape rows={tapeRows} />
    </div>
  );
}
