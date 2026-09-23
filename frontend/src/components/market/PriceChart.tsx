import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { LineSeries, PriceScaleMode, createChart } from "lightweight-charts";
import type { IChartApi, ISeriesApi, LineData, UTCTimestamp } from "lightweight-charts";

import { Skeleton } from "@/components/ui/skeleton";
import { buildChartOptions, chartSeriesColor } from "@/components/market/chartTheme";

export interface PriceChartSeries {
  id: string;
  label: string;
  points: LineData[];
  /** Точность цены (`seriesPrecision` из исходных строк Decimal); по умолчанию 2. */
  precision?: number;
}

export type PriceChartMode = "absolute" | "percent";
export type PriceChartScale = "intraday" | "daily";

export interface PriceChartHandle {
  /** Живой тик мимо React — вызывается из `useTradeStream({ onTrade })`. */
  update: (seriesId: string, point: LineData) => void;
}

export interface PriceChartProps {
  series: PriceChartSeries[];
  mode?: PriceChartMode;
  scale?: PriceChartScale;
  height?: number;
  /** Данные ещё грузятся — скелетон поверх графика, не пустой холст. */
  loading?: boolean;
  /** Подпись для пустого состояния (данных за период нет). */
  emptyLabel?: string;
}

/**
 * Обёртка над `lightweight-charts` через `useRef`: обновление серии —
 * императивное (`series.update()`), в обход рендера React. Каждый живой
 * тик иначе стоил бы перерисовки всего дерева компонентов.
 */
export const PriceChart = forwardRef<PriceChartHandle, PriceChartProps>(function PriceChart(
  {
    series,
    mode = "absolute",
    scale = "intraday",
    height = 360,
    loading = false,
    emptyLabel = "Нет данных за выбранный период.",
  },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const lastTimeRef = useRef<Map<string, UTCTimestamp>>(new Map());
  const seriesOrderRef = useRef<string[]>([]);

  const scaleRef = useRef(scale);
  useEffect(() => {
    scaleRef.current = scale;
  }, [scale]);

  // Создание графика — один раз на монтирование. Тёмная/светлая тема
  // читается из CSS-переменных canvas'ом не умеет сам, поэтому пересборка
  // цветов идёт через MutationObserver за классом `.dark` на <html>.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return undefined;
    }

    const chart = createChart(container, {
      ...buildChartOptions(scaleRef.current),
      autoSize: true,
    });
    chartRef.current = chart;

    const observer = new MutationObserver(() => {
      chart.applyOptions(buildChartOptions(scaleRef.current));
      seriesOrderRef.current.forEach((id, index) => {
        seriesRef.current.get(id)?.applyOptions({ color: chartSeriesColor(index) });
      });
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current.clear();
      lastTimeRef.current.clear();
      seriesOrderRef.current = [];
    };
  }, []);

  // Смена шкалы (intraday/daily) — формат оси, без пересоздания графика.
  useEffect(() => {
    chartRef.current?.applyOptions(buildChartOptions(scale));
  }, [scale]);

  // Синхронизация набора серий и их данных с пропом `series`.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    const nextIds = new Set(series.map((item) => item.id));
    for (const [id, api] of seriesRef.current) {
      if (!nextIds.has(id)) {
        chart.removeSeries(api);
        seriesRef.current.delete(id);
        lastTimeRef.current.delete(id);
      }
    }

    series.forEach((item, index) => {
      const precision = item.precision ?? 2;
      const priceFormat = {
        type: "price" as const,
        precision,
        minMove: 1 / 10 ** precision,
      };
      let api = seriesRef.current.get(item.id);
      if (!api) {
        api = chart.addSeries(LineSeries, {
          color: chartSeriesColor(index),
          lineWidth: 2,
          title: item.label,
          priceFormat,
        });
        seriesRef.current.set(item.id, api);
      } else {
        api.applyOptions({ color: chartSeriesColor(index), title: item.label, priceFormat });
      }
      api.setData(item.points);
      const last = item.points.at(-1);
      if (last) {
        lastTimeRef.current.set(item.id, last.time as UTCTimestamp);
      } else {
        lastTimeRef.current.delete(item.id);
      }
    });

    seriesOrderRef.current = series.map((item) => item.id);

    chart.priceScale("right").applyOptions({
      mode: mode === "percent" ? PriceScaleMode.Percentage : PriceScaleMode.Normal,
    });
  }, [series, mode]);

  useImperativeHandle(
    ref,
    () => ({
      update: (seriesId, point) => {
        const api = seriesRef.current.get(seriesId);
        if (!api) {
          return;
        }
        const lastTime = lastTimeRef.current.get(seriesId);
        const pointTime = point.time as UTCTimestamp;
        if (lastTime !== undefined && pointTime < lastTime) {
          // SSE не гарантирует строгий порядок между пачками отбора
          // "последние N на тикер" — тик не по порядку просто отбрасываем,
          // а не роняем весь график исключением из `series.update()`.
          return;
        }
        try {
          api.update(point);
          lastTimeRef.current.set(seriesId, pointTime);
        } catch (error: unknown) {
          console.warn("PriceChart: не удалось применить тик", error);
        }
      },
    }),
    [],
  );

  const isEmpty = !loading && series.every((item) => item.points.length === 0);

  return (
    <div className="relative w-full" style={{ height }}>
      <div ref={containerRef} className="absolute inset-0" />
      {/* z-10: lightweight-charts ставит собственным canvas'ам/логотипу
          явный z-index, простого порядка в DOM недостаточно, чтобы
          оверлей оказался поверх графика. */}
      {loading && <Skeleton className="absolute inset-0 z-10" />}
      {isEmpty && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-md border border-dashed bg-card">
          <p className="text-sm text-muted-foreground">{emptyLabel}</p>
        </div>
      )}
    </div>
  );
});
