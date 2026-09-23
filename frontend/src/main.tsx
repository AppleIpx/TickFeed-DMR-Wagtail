import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import { router } from "./app/router";
import { TooltipProvider } from "./components/ui/tooltip";
import { queryClient } from "./query/queryClient";
import "./styles/index.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("В index.html нет элемента #root");
}

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
      {/* Devtools — девзависимость: прод-сборки в скоупе этапа 10 нет. */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
);
