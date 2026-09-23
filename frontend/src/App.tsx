import { useMemo, useRef, useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { FreshnessBadge } from "@/components/market/FreshnessBadge";
import type { PriceChartHandle, PriceChartScale } from "@/components/market/PriceChart";
import { PriceChart } from "@/components/market/PriceChart";
import { RateTable } from "@/components/market/RateTable";
import {
  linearPointsToSeries,
  seriesPrecision,
  stockClosePrices,
  stockHistoryToSeries,
  tradeEventToMinutePoint,
} from "@/components/market/series";
import { StreamStatus } from "@/components/market/StreamStatus";
import { ThemeToggle } from "@/components/market/ThemeToggle";
import { TradeTape, cryptoTradeToRow, stockTradeToRow } from "@/components/market/TradeTape";
import { useCryptoAssets, useCryptoCurrent, useCryptoIntraday, useCryptoTrades } from "@/query/hooks/crypto";
import { useFiatRates } from "@/query/hooks/fiat";
import { useStockAssets, useStockCurrent, useStockHistory, useStockIntraday } from "@/query/hooks/stocks";
import { useCryptoTradeStream, useStockTradeStream } from "@/query/hooks/useTradeStream";

const COMPARE_COUNT = 2;

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  );
}

function CryptoSection() {
  const assets = useCryptoAssets();
  const symbol = assets.data?.find((asset) => asset.is_active)?.symbol;

  const current = useCryptoCurrent(symbol);
  const intraday = useCryptoIntraday(symbol);
  const trades = useCryptoTrades(symbol, { limit: 20 });

  const chartRef = useRef<PriceChartHandle>(null);
  const stream = useCryptoTradeStream({
    tickers: symbol ? [symbol] : undefined,
    enabled: symbol !== undefined,
    bufferSize: 20,
    onTrade: (event) => {
      chartRef.current?.update(event.symbol, tradeEventToMinutePoint(event));
    },
  });

  const series = useMemo(() => {
    if (!symbol || !intraday.data) {
      return [];
    }
    const points = intraday.data.points;
    return [
      {
        id: symbol,
        label: symbol,
        points: linearPointsToSeries(points),
        precision: seriesPrecision(points.map((point) => point.price)),
      },
    ];
  }, [symbol, intraday.data]);

  const tapeRows = useMemo(() => {
    const live = stream.trades.map(cryptoTradeToRow);
    const liveIds = new Set(live.map((row) => row.id));
    const rest = (trades.data?.items ?? [])
      .map(cryptoTradeToRow)
      .filter((row) => !liveIds.has(row.id));
    return [...live, ...rest].slice(0, 30);
  }, [stream.trades, trades.data]);

  return (
    <SectionCard
      title="Крипта — тиковый поток"
      description="Binance, push с биржи, задержка ~0. Живые тики применяются к графику мимо React."
    >
      {!symbol ? (
        <Skeleton className="h-72 w-full" />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-lg font-semibold tabular">{symbol}</span>
            {current.data && <FreshnessBadge freshness={current.data.freshness} sourceHint="Binance WebSocket" />}
          </div>
          <PriceChart ref={chartRef} series={series} scale="intraday" height={280} />
          <StreamStatus
            status={stream.status}
            lastHeartbeatAt={stream.lastHeartbeatAt}
            warning={stream.warning}
            fatal={stream.fatal}
          />
          <TradeTape rows={tapeRows} />
        </>
      )}
    </SectionCard>
  );
}

function StocksSection() {
  const assets = useStockAssets();
  const secids = useMemo(
    () =>
      (assets.data ?? [])
        .filter((asset) => asset.is_active)
        .slice(0, COMPARE_COUNT)
        .map((asset) => asset.symbol),
    [assets.data],
  );
  const [secidA, secidB] = secids;

  const [scale, setScale] = useState<PriceChartScale>("intraday");
  const [mode, setMode] = useState<"absolute" | "percent">("percent");

  const currentA = useStockCurrent(secidA);
  const intradayA = useStockIntraday(secidA, { enabled: scale === "intraday" });
  const intradayB = useStockIntraday(secidB, { enabled: scale === "intraday" });
  const historyA = useStockHistory(secidA, {}, { enabled: scale === "daily" });
  const historyB = useStockHistory(secidB, {}, { enabled: scale === "daily" });

  const chartRef = useRef<PriceChartHandle>(null);
  const stream = useStockTradeStream({
    tickers: secids.length > 0 ? secids : undefined,
    enabled: secids.length > 0,
    bufferSize: 20,
    onTrade: (event) => {
      chartRef.current?.update(event.secid, tradeEventToMinutePoint(event));
    },
  });

  const series = useMemo(() => {
    if (scale === "intraday") {
      return [
        secidA && intradayA.data
          ? {
              id: secidA,
              label: secidA,
              points: linearPointsToSeries(intradayA.data.points),
              precision: seriesPrecision(intradayA.data.points.map((p) => p.price)),
            }
          : undefined,
        secidB && intradayB.data
          ? {
              id: secidB,
              label: secidB,
              points: linearPointsToSeries(intradayB.data.points),
              precision: seriesPrecision(intradayB.data.points.map((p) => p.price)),
            }
          : undefined,
      ].filter((item): item is NonNullable<typeof item> => item !== undefined);
    }
    return [
      secidA && historyA.data
        ? {
            id: secidA,
            label: secidA,
            points: stockHistoryToSeries(historyA.data),
            precision: seriesPrecision(stockClosePrices(historyA.data)),
          }
        : undefined,
      secidB && historyB.data
        ? {
            id: secidB,
            label: secidB,
            points: stockHistoryToSeries(historyB.data),
            precision: seriesPrecision(stockClosePrices(historyB.data)),
          }
        : undefined,
    ].filter((item): item is NonNullable<typeof item> => item !== undefined);
  }, [scale, secidA, secidB, intradayA.data, intradayB.data, historyA.data, historyB.data]);

  const tapeRows = useMemo(() => stream.trades.map(stockTradeToRow), [stream.trades]);

  return (
    <SectionCard
      title="Акции — сравнение бумаг"
      description="MOEX, опрос раз в минуту + задержка ISS ~15 минут — честно помечена ниже."
    >
      {secids.length === 0 ? (
        <Skeleton className="h-72 w-full" />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm text-muted-foreground">
              {secids.join(" · ")}
            </span>
            {currentA.data && (
              <FreshnessBadge freshness={currentA.data.freshness} sourceHint="MOEX ISS, бесплатный доступ" />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Tabs value={scale} onValueChange={(value) => setScale(value as PriceChartScale)}>
              <TabsList>
                <TabsTrigger value="intraday">Внутри дня</TabsTrigger>
                <TabsTrigger value="daily">История</TabsTrigger>
              </TabsList>
            </Tabs>
            <ToggleGroup
              type="single"
              value={mode}
              onValueChange={(value) => value && setMode(value as "absolute" | "percent")}
              variant="outline"
              size="sm"
            >
              <ToggleGroupItem value="percent">%</ToggleGroupItem>
              <ToggleGroupItem value="absolute">₽</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <PriceChart ref={chartRef} series={series} mode={mode} scale={scale} height={280} />
          <StreamStatus
            status={stream.status}
            lastHeartbeatAt={stream.lastHeartbeatAt}
            warning={stream.warning}
            fatal={stream.fatal}
          />
          <TradeTape rows={tapeRows} emptyLabel="Сделок в живом потоке пока не было." />
        </>
      )}
    </SectionCard>
  );
}

function FiatSection() {
  const rates = useFiatRates();

  return (
    <SectionCard
      title="Валюты — курсы ЦБ РФ"
      description="Одна точка в сутки, живого графика нет по решению этапа 9 — таблица и спарклайн."
    >
      {rates.isPending && <Skeleton className="h-48 w-full" />}
      {rates.isError && <p className="text-sm text-destructive">Ошибка: {rates.error.message}</p>}
      {rates.data && <RateTable rates={rates.data} />}
    </SectionCard>
  );
}

export default function App() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">TickFeedDmr</h1>
          <p className="text-sm text-muted-foreground">
            Дашборд котировок — этап 10.3, витрина компонентов на живых данных.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <CryptoSection />
      <StocksSection />
      <FiatSection />

      <footer className="pb-4 text-center text-xs text-muted-foreground">
        Графики построены на{" "}
        <a
          href="https://www.tradingview.com/lightweight-charts/"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          Lightweight Charts™
        </a>{" "}
        от TradingView, распространяется по лицензии Apache License 2.0.
      </footer>
    </div>
  );
}
