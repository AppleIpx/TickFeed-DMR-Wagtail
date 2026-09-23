import { NavLink, Outlet } from "react-router";

import { ThemeToggle } from "@/components/market/ThemeToggle";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/crypto", label: "Крипта" },
  { to: "/stocks", label: "Акции" },
  { to: "/fiat", label: "Валюты" },
];

/** Общая шапка/навигация/подвал для всех экранов дашборда. */
export function AppShell() {
  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">TickFeedDmr</h1>
          <p className="text-sm text-muted-foreground">Дашборд котировок</p>
        </div>
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
          <ThemeToggle />
        </nav>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

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
