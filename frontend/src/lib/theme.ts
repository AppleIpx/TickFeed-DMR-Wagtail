import { useEffect, useState } from "react";

/**
 * Тема оформления: светлая/тёмная/системная. Класс `.dark` на `<html>`
 * управляет токенами из `styles/tokens.css`. `localStorage` — только
 * удобство конкретного браузера (запомнить выбор), не источник истины:
 * при недоступности (приватный режим и т.п.) тихо откатываемся на
 * системную тему.
 */

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "tickfeeddmr:theme";
const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia(DARK_MEDIA_QUERY).matches ? "dark" : "light";
}

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // localStorage недоступен — используем системную тему.
  }
  return "system";
}

function resolveTheme(theme: Theme): ResolvedTheme {
  return theme === "system" ? getSystemTheme() : theme;
}

function applyResolvedTheme(resolved: ResolvedTheme): void {
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

export interface UseThemeResult {
  theme: Theme;
  resolved: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

export function useTheme(): UseThemeResult {
  const [theme, setTheme] = useState<Theme>(() => readStoredTheme());
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(theme));

  useEffect(() => {
    const next = resolveTheme(theme);
    setResolved(next);
    applyResolvedTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // недоступно — выбор темы просто не переживёт перезагрузку страницы.
    }
  }, [theme]);

  useEffect(() => {
    if (theme !== "system") {
      return undefined;
    }
    const media = window.matchMedia(DARK_MEDIA_QUERY);
    const onChange = () => {
      const next = getSystemTheme();
      setResolved(next);
      applyResolvedTheme(next);
    };
    media.addEventListener("change", onChange);
    return () => {
      media.removeEventListener("change", onChange);
    };
  }, [theme]);

  return { theme, resolved, setTheme };
}
