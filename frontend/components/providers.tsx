"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Retrying a 401/404 three times with backoff just made every
            // broken page hang for ~7s before rendering its error. Client
            // errors are not transient — only retry 5xx/network faults, once.
            retry: (failureCount, error) => {
              const status = (error as ApiError)?.status;
              if (typeof status === "number" && status >= 400 && status < 500) {
                return false;
              }
              return failureCount < 1;
            },
            retryDelay: 1_000,
          },
          mutations: { retry: false },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="dark"
        enableSystem={false}
        disableTransitionOnChange
      >
        {children}
        <Toaster position="bottom-right" richColors closeButton />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
