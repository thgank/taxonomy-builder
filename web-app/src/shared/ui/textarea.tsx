import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-28 w-full rounded-[24px] border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-4 py-3 text-sm text-[color:var(--color-ink)] outline-none transition placeholder:text-[color:var(--color-muted-soft)] focus:border-[color:var(--color-border-strong)] focus:bg-white focus:shadow-[0_0_0_4px_var(--color-accent-soft)]",
        className,
      )}
      {...props}
    />
  );
}
