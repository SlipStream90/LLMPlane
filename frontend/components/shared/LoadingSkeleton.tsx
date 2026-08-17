import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  variant?: "card" | "table" | "chart" | "page";
  count?: number;
  className?: string;
}

export function LoadingSkeleton({ variant = "card", count = 1, className }: LoadingSkeletonProps) {
  return (
    <div className={cn("space-y-4", className)}>
      {Array.from({ length: count }).map((_, i) => {
        switch (variant) {
          case "card":
            return (
              <div key={i} className="surface p-5 space-y-4">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-8 w-1/2" />
                <Skeleton className="h-3 w-2/3" />
              </div>
            );
          case "table":
            return (
              <div key={i} className="space-y-3">
                <Skeleton className="h-10 w-full rounded-lg" />
                {Array.from({ length: 5 }).map((_, j) => (
                  <Skeleton key={j} className="h-12 w-full rounded-lg" />
                ))}
              </div>
            );
          case "chart":
            return (
              <div key={i} className="surface p-5">
                <Skeleton className="h-4 w-1/4 mb-4" />
                <Skeleton className="h-64 w-full rounded-lg" />
              </div>
            );
          case "page":
            return (
              <div key={i} className="page-container">
                <Skeleton className="h-8 w-1/4" />
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <Skeleton key={j} className="h-28 rounded-xl" />
                  ))}
                </div>
                <Skeleton className="h-96 w-full rounded-xl" />
              </div>
            );
        }
      })}
    </div>
  );
}
