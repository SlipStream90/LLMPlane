import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

function Skeleton({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return <div className={cn("skeleton rounded-md", className)} style={style} />;
}

export { Skeleton };
