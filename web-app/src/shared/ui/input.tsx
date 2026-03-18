import type { InputHTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-4 text-sm text-[color:var(--color-ink)] outline-none transition placeholder:text-[color:var(--color-muted-soft)] focus:border-[color:var(--color-border-strong)] focus:bg-white focus:shadow-[0_0_0_4px_var(--color-accent-soft)]",
        className,
      )}
      {...props}
    />
  );
}
