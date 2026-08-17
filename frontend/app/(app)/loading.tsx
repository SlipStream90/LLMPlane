import { LoadingPage } from "@/components/ui/cards";

/* Route-level suspense fallback. Previously hand-rolled with `.kpi-card`, a
   class that no longer exists — it now shares the same skeleton as every
   in-page loading state so the two cannot drift apart. */
export default function Loading() {
  return <LoadingPage />;
}
