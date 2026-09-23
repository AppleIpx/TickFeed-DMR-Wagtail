/**
 * Мини-график строкой SVG для `RateTable` — canvas на каждую строку
 * таблицы избыточен, чистый SVG дешевле и не требует lightweight-charts.
 */

const WIDTH = 96;
const HEIGHT = 28;
const PADDING = 2;

export interface SparklineProps {
  values: readonly number[];
  positive?: boolean;
}

export function Sparkline({ values, positive }: SparklineProps) {
  if (values.length < 2) {
    return <div style={{ width: WIDTH, height: HEIGHT }} />;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((value, index) => {
    const x = PADDING + (index / (values.length - 1)) * (WIDTH - PADDING * 2);
    const y = HEIGHT - PADDING - ((value - min) / range) * (HEIGHT - PADDING * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const trendUp = (values.at(-1) ?? 0) >= (values[0] ?? 0);
  const colorClass = (positive ?? trendUp) ? "stroke-realtime" : "stroke-sell";

  return (
    <svg
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className={colorClass}
      aria-hidden
    >
      <polyline
        points={points.join(" ")}
        fill="none"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
