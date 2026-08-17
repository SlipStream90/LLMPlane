"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("App error:", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] grid place-items-center px-6">
      <div className="surface max-w-md w-full p-6 text-center">
        <span className="grid place-items-center w-11 h-11 mx-auto rounded-lg bg-danger-subtle text-danger">
          <AlertTriangle className="w-5 h-5" />
        </span>

        <h2 className="text-base font-semibold tracking-tight mt-4">Something went wrong</h2>
        <p className="text-sm text-muted-foreground mt-2 break-words">
          {error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="text-[0.6875rem] font-mono text-subtle-foreground mt-2">
            digest {error.digest}
          </p>
        )}

        <button
          onClick={reset}
          className="inline-flex items-center gap-2 mt-5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors"
        >
          <RotateCw className="w-3.5 h-3.5" />
          Try again
        </button>
      </div>
    </div>
  );
}
