import type { HTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "metric-card p-6",
        className,
      )}
      {...props}
    />
  );
}
