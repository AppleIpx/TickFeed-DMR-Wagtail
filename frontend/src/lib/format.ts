/**
 * Форматирование цен/объёмов/времени для дашборда.
 *
 * Цены с бэкенда приходят строками (`Decimal` кодируется msgspec как
 * строка, см. CLAUDE.md/этап 8a) — здесь и только здесь они превращаются
 * в число, и только для отображения.
 */

const MOSCOW_TZ = "Europe/Moscow";

/** Число значащих десятичных знаков строки цены, без хвостовых нулей. */
export function decimalPrecision(value: string): number {
  const dotIndex = value.indexOf(".");
  if (dotIndex === -1) {
    return 0;
  }
  const fraction = value.slice(dotIndex + 1).replace(/0+$/, "");
  return fraction.length;
}

/** Цена с точностью, унаследованной от исходной строки (2..8 знаков). */
export function formatPrice(value: string): string {
  const precision = Math.max(2, Math.min(decimalPrecision(value), 8));
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return value;
  }
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  }).format(number);
}

export function formatVolume(value: string | number): string {
  const number = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(number)) {
    return String(value);
  }
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 4 }).format(number);
}

const timeFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW_TZ,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW_TZ,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  timeZone: MOSCOW_TZ,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

/** `HH:MM:SS` по Москве — для строки ленты сделок. */
export function formatMoscowTime(iso: string): string {
  return timeFormatter.format(new Date(iso));
}

/** `ДД.MM.ГГГГ HH:MM МСК` — для подписи «обновлено в …». */
export function formatMoscowDateTime(iso: string): string {
  return `${dateTimeFormatter.format(new Date(iso))} МСК`;
}

/** `ДД.MM.ГГГГ` по Москве — для дневных точек истории/курсов ЦБ. */
export function formatMoscowDate(iso: string): string {
  return dateFormatter.format(new Date(iso));
}

/** Задержка источника в человекочитаемом виде (`FreshnessBadge`). */
export function formatDelay(seconds: number): string {
  if (seconds <= 0) {
    return "в реальном времени";
  }
  if (seconds < 60) {
    return "меньше минуты";
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes} мин`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours} ч`;
  }
  const days = Math.round(hours / 24);
  return `${days} ${days === 1 ? "день" : "дн."}`;
}
