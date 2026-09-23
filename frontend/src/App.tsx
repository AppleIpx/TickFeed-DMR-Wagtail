import { useState } from "react";

import { useCryptoAssets } from "@/query/hooks/crypto";
import { useCryptoTradeStream } from "@/query/hooks/useTradeStream";

function parseTickers(raw: string): string[] {
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

export default function App() {
  const [filterInput, setFilterInput] = useState("");
  const [tickers, setTickers] = useState<string[]>([]);

  const assets = useCryptoAssets();
  const stream = useCryptoTradeStream({ tickers, bufferSize: 20 });

  return (
    <main>
      <h1>TickFeedDmr</h1>
      <p>
        Смоук-экран слоя данных (этап 10.2). Бэкенд:{" "}
        <code>{import.meta.env.VITE_API_BASE_URL}</code>
      </p>

      <section>
        <h2>Крипто-активы (REST)</h2>
        {assets.isPending && <p>Загружаю список…</p>}
        {assets.isError && <p>Ошибка: {assets.error.message}</p>}
        {assets.data && (
          <ul>
            {assets.data.map((asset) => (
              <li key={asset.symbol}>
                {asset.symbol} — {asset.display_name}
                {asset.is_active ? "" : " (выключен)"}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Живой поток сделок (SSE)</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setTickers(parseTickers(filterInput));
          }}
        >
          <label>
            Фильтр <code>?symbols=</code> (пусто — все активные):{" "}
            <input
              value={filterInput}
              onChange={(event) => {
                setFilterInput(event.target.value);
              }}
              placeholder="BTC,ETH"
            />
          </label>{" "}
          <button type="submit">Переоткрыть поток</button>
        </form>

        <p>
          Состояние: <strong>{stream.status}</strong>
          {stream.lastHeartbeatAt && <> · heartbeat: {stream.lastHeartbeatAt}</>}
        </p>
        {stream.warning && (
          <p>
            Предупреждение: {stream.warning.detail} (не найдены:{" "}
            {stream.warning.unknown.join(", ")})
          </p>
        )}
        {stream.fatal && <p>Поток остановлен: {stream.fatal.message}</p>}

        <ol>
          {stream.trades.map((trade) => (
            <li key={`${trade.symbol}-${trade.trade_id}`}>
              {trade.timestamp} · {trade.symbol} · {trade.side} · {trade.price} ·{" "}
              {trade.volume} · лаг {trade.data_delay_seconds} с
            </li>
          ))}
        </ol>
        {stream.trades.length === 0 && <p>Сделок пока не было.</p>}
      </section>
    </main>
  );
}
