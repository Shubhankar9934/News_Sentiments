import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import { App } from "./App";
import "./styles/index.css";

function applyStoredTheme() {
  try {
    const raw = localStorage.getItem("finresearch-theme");
    if (!raw) return;
    const parsed = JSON.parse(raw) as { state?: { theme?: string } };
    document.documentElement.classList.toggle("dark", parsed.state?.theme === "dark");
  } catch {
    // Ignore malformed persisted theme.
  }
}

applyStoredTheme();

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <Suspense fallback={<div className="p-6 text-sm">Loading…</div>}>
        <App />
      </Suspense>
      <Toaster richColors closeButton />
    </QueryClientProvider>
  </StrictMode>
);
