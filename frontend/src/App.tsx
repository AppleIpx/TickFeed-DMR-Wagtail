import { useEffect, useState } from "react";


type PingState =
  | { status: "loading" }
  | { status: "ok"; assets: number }
  | { status: "error"; message: string };

export default function App() {
  const [ping, setPing] = useState<PingState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${import.meta.env.VITE_API_BASE_URL}/api/crypto/assets/`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload: unknown = await response.json();
        if (!Array.isArray(payload)) {
          throw new Error("Ожидался список активов");
        }
        setPing({ status: "ok", assets: payload.length });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setPing({
          status: "error",
          message: error instanceof Error ? error.message : String(error),
        });
      });

    return () => {
      controller.abort();
    };
  }, []);

  return (
    <main>
      <h1>TickFeedDmr</h1>
      <p>Скелет фронтенда, этап 10.1. Экраны появятся на этапе 10.4.</p>
      <p>
        Бэкенд: <code>{import.meta.env.VITE_API_BASE_URL}</code>
      </p>
      {ping.status === "loading" && <p>Проверяю связь с API…</p>}
      {ping.status === "ok" && (
        <p>
          API отвечает: активных крипто-пар — <strong>{ping.assets}</strong>
        </p>
      )}
      {ping.status === "error" && (
        <p>
          API недоступен: <strong>{ping.message}</strong> (смотреть консоль —
          ошибка CORS видна только там)
        </p>
      )}
    </main>
  );
}
