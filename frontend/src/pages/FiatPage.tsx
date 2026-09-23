import { useMemo } from "react";
import { useSearchParams } from "react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { PeriodToggle } from "@/components/market/PeriodToggle";
import { PriceChart } from "@/components/market/PriceChart";
import { RateTable } from "@/components/market/RateTable";
import { fiatHistoryToSeries, seriesPrecision } from "@/components/market/series";
import { parsePeriod, periodToFromDate, withParam } from "@/lib/searchParams";
import { useFiatHistory, useFiatRates } from "@/query/hooks/fiat";

export function FiatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rates = useFiatRates();

  const codes = useMemo(() => (rates.data ?? []).map((rate) => rate.iso_code), [rates.data]);
  const requested = searchParams.get("code");
  const code = requested && codes.includes(requested) ? requested : codes[0];

  const period = parsePeriod(searchParams.get("period"));
  const history = useFiatHistory(code, { from: periodToFromDate(period) });

  const series = useMemo(() => {
    if (!code) {
      return [];
    }
    const points = history.data ?? [];
    return [
      {
        id: code,
        label: code,
        points: fiatHistoryToSeries(points),
        precision: seriesPrecision(points.map((point) => point.rate)),
      },
    ];
  }, [code, history.data]);

  if (rates.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Не удалось загрузить курсы ЦБ: {rates.error.message}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        ЦБ РФ публикует курс раз в сутки — живого потока по решению этапа 9 нет, ниже таблица и
        дневная история выбранной валюты.
      </p>

      <RateTable
        rates={rates.data ?? []}
        selected={code}
        onSelect={(iso) => setSearchParams(withParam(searchParams, "code", iso))}
      />

      {code && (
        <>
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium">{code} — история курса</span>
            <PeriodToggle
              value={period}
              onChange={(next) => setSearchParams(withParam(searchParams, "period", next))}
            />
          </div>
          <PriceChart series={series} scale="daily" height={280} loading={history.isPending} />
        </>
      )}
    </div>
  );
}
