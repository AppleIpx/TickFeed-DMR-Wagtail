import { ColorType } from "lightweight-charts";
import type {
  ChartOptions,
  DeepPartial,
  Time,
  TickMarkFormatter,
  TimeFormatterFn,
  UTCTimestamp,
} from "lightweight-charts";

/**
 * `lightweight-charts` рисует в `<canvas>` и не видит CSS/Tailwind —
 * цвета читаются из вычисленных CSS-переменных (`styles/tokens.css`) в
 * момент создания графика и при каждой смене темы. Ни одного hex здесь и
 * в компонентах, использующих эту тему, не должно быть.
 */

const MOSCOW_TZ = "Europe/Moscow";

let colorCanvasCtx: CanvasRenderingContext2D | null = null;

/**
 * `lightweight-charts` кое-где считает цвет сам (например, серость фона
 * для выбора светлого/тёмного логотипа атрибуции) через собственный
 * парсер, который не знает `oklch()` — падает `Failed to parse color`
 * (проверено живьём в браузере). Canvas 2D `fillStyle` парсит `oklch`
 * нативно, поэтому цвет прогоняется через 1×1 canvas и возвращается уже
 * конкретным `rgb()`/`rgba()`, который понимает любой парсер.
 */
function resolveCssColor(value: string): string {
  if (!colorCanvasCtx) {
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    colorCanvasCtx = canvas.getContext("2d", { willReadFrequently: true });
  }
  if (!colorCanvasCtx) {
    return value;
  }
  colorCanvasCtx.clearRect(0, 0, 1, 1);
  colorCanvasCtx.fillStyle = value;
  colorCanvasCtx.fillRect(0, 0, 1, 1);
  const [r = 0, g = 0, b = 0, a = 255] = colorCanvasCtx.getImageData(0, 0, 1, 1).data;
  return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`;
}

function readVar(name: string): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return resolveCssColor(raw);
}

/** oklch(...) переменные из tokens.css как есть — canvas 2D их понимает. */
export function readChartColor(token: string): string {
  return readVar(`--${token}`);
}

export const CHART_SERIES_TOKENS = [
  "chart-1",
  "chart-2",
  "chart-3",
  "chart-4",
  "chart-5",
  "chart-6",
] as const;

/** Цвет N-й серии по кругу — палитра сравнения бумаг рассчитана на 6 штук. */
export function chartSeriesColor(index: number): string {
  const token = CHART_SERIES_TOKENS[index % CHART_SERIES_TOKENS.length] ?? "chart-1";
  return readChartColor(token);
}

/** Все данные в проекте — секундные `UTCTimestamp`, бизнес-дни не используются. */
function toDate(time: Time): Date {
  return new Date((time as UTCTimestamp) * 1000);
}

const timeFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW_TZ,
  hour: "2-digit",
  minute: "2-digit",
});

const dayFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW_TZ,
  day: "2-digit",
  month: "2-digit",
});

const fullDateFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW_TZ,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Метки оси времени — всегда по Москве, независимо от таймзоны браузера. */
export function chartTickMarkFormatter(scale: "intraday" | "daily"): TickMarkFormatter {
  return (time) => {
    const date = toDate(time);
    return scale === "intraday" ? timeFormatter.format(date) : dayFormatter.format(date);
  };
}

/** Подпись времени в перекрестье (`crosshair`) — полная дата и минуты по Москве. */
export function chartCrosshairTimeFormatter(): TimeFormatterFn<Time> {
  return (time) => fullDateFormatter.format(toDate(time));
}

/** Базовые опции графика, собранные из текущей темы (пересобрать при смене темы). */
export function buildChartOptions(scale: "intraday" | "daily"): DeepPartial<ChartOptions> {
  return {
    layout: {
      background: { type: ColorType.Solid, color: readVar("--card") },
      textColor: readVar("--muted-foreground"),
      // Атрибуция TradingView обязательна условиями лицензии Apache 2.0 —
      // не выключать, даже если она "мешает" вёрстке.
      attributionLogo: true,
    },
    grid: {
      vertLines: { color: readVar("--border") },
      horzLines: { color: readVar("--border") },
    },
    rightPriceScale: {
      borderColor: readVar("--border"),
    },
    timeScale: {
      borderColor: readVar("--border"),
      tickMarkFormatter: chartTickMarkFormatter(scale),
    },
    localization: {
      timeFormatter: chartCrosshairTimeFormatter(),
    },
    crosshair: {
      vertLine: { color: readVar("--muted-foreground") },
      horzLine: { color: readVar("--muted-foreground") },
    },
  };
}
