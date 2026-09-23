import { useMemo, useRef } from "react";
import { useSearchParams } from "react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PeriodToggle } from "@/components/market/PeriodToggle";
import type { PriceChartHandle, PriceChartSeries } from "@/components/market/PriceChart";
import { PriceChart } from "@/components/market/PriceChart";
import {
  linearPointsToSeries,
  seriesPrecision,
  stockClosePrices,
  stockHistoryToSeries,
  tradeEventToMinutePoint,
} from "@/components/market/series";
import { StockQuoteTable } from "@/components/market/StockQuoteTable";
import { StreamStatus } from "@/components/market/StreamStatus";
import { TickerPicker } from "@/components/market/TickerPicker";
import { TradeTape, mergeTapeRows, stockTradeToRow } from "@/components/market/TradeTape";
import {
  parseMode,
  parsePeriod,
  parseScale,
  parseTickerList,
  periodToFromDate,
  tickerListToParam,
  withParam,
} from "@/lib/searchParams";
import { useStockAssets, useStockHistoryMany, useStockIntradayMany } from "@/query/hooks/stocks";
import { useStockTradeStream } from "@/query/hooks/useTradeStream";

const DEFAULT_COMPARE_COUNT = 2;
const MAX_COMPARE_COUNT = 6;

export function StocksPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const assets = useStockAssets();

  const activeSecids = useMemo(
    () => (assets.data ?? []).filter((asset) => asset.is_active).map((asset) => asset.symbol),
    [assets.data],
  );

  const requested = parseTickerList(searchParams.get("secids"));
  const secids = useMemo(() => {
    const valid = requested.filter((secid) => activeSecids.includes(secid));
    if (valid.length > 0) {
      return valid.slice(0, MAX_COMPARE_COUNT);
    }
    return activeSecids.slice(0, DEFAULT_COMPARE_COUNT);
  }, [requested, activeSecids]);

  // Живая лента/поток — только по бумагам с track_trades; график и
  // котировки работают для любой выбранной бумаги.
  const tradableSecids = useMemo(
    () => secids.filter((secid) => assets.data?.find((asset) => asset.symbol === secid)?.track_trades),
    [secids, assets.data],
  );

  const scale = parseScale(searchParams.get("view"));
  const mode = parseMode(searchParams.get("mode"));
  const period = parsePeriod(searchParams.get("period"));

  const intradayResults = useStockIntradayMany(scale === "intraday" ? secids : []);
  const historyResults = useStockHistoryMany(
    scale === "daily" ? secids : [],
    { from: periodToFromDate(period) },
  );

  const chartRef = useRef<PriceChartHandle>(null);
  const stream = useStockTradeStream({
    tickers: tradableSecids.length > 0 ? tradableSecids : undefined,
    enabled: tradableSecids.length > 0,
    bufferSize: 30,
    onTrade: (event) => {
      if (scale === "intraday") {
        chartRef.current?.update(event.secid, tradeEventToMinutePoint(event));
      }
    },
  });

  const series = useMemo<PriceChartSeries[]>(() => {
    if (scale === "intraday") {
      return secids.map((secid, index) => {
        const points = intradayResults[index]?.data?.points ?? [];
        return {
          id: secid,
          label: secid,
          points: linearPointsToSeries(points),
          precision: seriesPrecision(points.map((point) => point.price)),
        };
      });
    }
    return secids.map((secid, index) => {
      const points = historyResults[index]?.data ?? [];
      return {
        id: secid,
        label: secid,
        points: stockHistoryToSeries(points),
        precision: seriesPrecision(stockClosePrices(points)),
      };
    });
  }, [secids, scale, intradayResults, historyResults]);

  // `assets.isPending` отдельно: до того как список акций пришёл, `secids`
  // пуст, а `useQueries` на пустом массиве — `[]`, и `.some(isPending)` на
  // нём ложно `false`. Без этой строки график на долю секунды показал бы
  // "нет данных" вместо скелетона, пока грузится сам список, а не котировки.
  const isLoading =
    assets.isPending ||
    (scale === "intraday"
      ? intradayResults.some((result) => result.isPending)
      : historyResults.some((result) => result.isPending));

  const tapeRows = useMemo(
    () => mergeTapeRows(stream.trades.map((event) => stockTradeToRow(event, event.secid)), []),
    [stream.trades],
  );

  const updateSecids = (next: string[]) => {
    setSearchParams(withParam(searchParams, "secids", tickerListToParam(next)));
  };

  if (assets.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Не удалось загрузить список акций: {assets.error.message}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <TickerPicker assets={assets.data ?? []} selected={secids} onChange={updateSecids} />

      <p className="text-sm text-muted-foreground">
        MOEX, опрос раз в минуту + задержка ISS ~15 минут — см. свежесть в таблице ниже.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          value={scale}
          onValueChange={(value) => setSearchParams(withParam(searchParams, "view", value))}
        >
          <TabsList>
            <TabsTrigger value="intraday">Внутри дня</TabsTrigger>
            <TabsTrigger value="daily">История</TabsTrigger>
          </TabsList>
        </Tabs>
        <ToggleGroup
          type="single"
          value={mode}
          onValueChange={(value) => {
            if (value) {
              setSearchParams(withParam(searchParams, "mode", value));
            }
          }}
          variant="outline"
          size="sm"
        >
          <ToggleGroupItem value="percent">%</ToggleGroupItem>
          <ToggleGroupItem value="absolute">₽</ToggleGroupItem>
        </ToggleGroup>
        {scale === "daily" && (
          <PeriodToggle
            value={period}
            onChange={(next) => setSearchParams(withParam(searchParams, "period", next))}
          />
        )}
      </div>

      <PriceChart ref={chartRef} series={series} mode={mode} scale={scale} height={320} loading={isLoading} />

      <StockQuoteTable secids={secids} />

      <StreamStatus
        status={stream.status}
        lastHeartbeatAt={stream.lastHeartbeatAt}
        warning={stream.warning}
        fatal={stream.fatal}
      />

      <TradeTape rows={tapeRows} emptyLabel="Сделок в живом потоке пока не было." />
    </div>
  );
}
