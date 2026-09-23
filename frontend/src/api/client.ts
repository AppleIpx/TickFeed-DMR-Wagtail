import createClient from "openapi-fetch";

import type { paths } from "@/api/schema";

const baseUrl = import.meta.env.VITE_API_BASE_URL;

if (!baseUrl) {
  throw new Error(
    "Не задан VITE_API_BASE_URL — базовый URL бэкенда (см. .env.development)",
  );
}

export const apiBaseUrl: string = baseUrl;

export const api = createClient<paths>({ baseUrl: apiBaseUrl });
