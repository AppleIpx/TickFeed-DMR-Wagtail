import { Navigate, createBrowserRouter } from "react-router";

import { AppShell } from "@/app/AppShell";
import { CryptoPage } from "@/pages/CryptoPage";
import { FiatPage } from "@/pages/FiatPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { StocksPage } from "@/pages/StocksPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/crypto" replace /> },
      { path: "crypto", element: <CryptoPage /> },
      { path: "stocks", element: <StocksPage /> },
      { path: "fiat", element: <FiatPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
