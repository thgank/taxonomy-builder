import type { LabelHTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn(
        "mb-2 block text-[13px] font-semibold uppercase tracking-[0.16em] text-[color:var(--color-muted)]",
        className,
      )}
      {...props}
    />
  );
}
