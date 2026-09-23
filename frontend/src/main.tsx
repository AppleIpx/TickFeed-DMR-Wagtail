import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { queryClient } from "./query/queryClient";
import "./styles/index.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("В index.html нет элемента #root");
}

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      {/* Devtools — девзависимость: прод-сборки в скоупе этапа 10 нет. */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
);
