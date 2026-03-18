import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/shared/lib/cn";

const buttonVariants = {
  primary:
    "border border-[color:var(--color-ink)] bg-[color:var(--color-ink)] text-white shadow-[0_10px_24px_rgba(23,23,23,0.14)] hover:bg-[color:var(--color-ink-soft)]",
  secondary:
    "border border-[color:var(--color-border-strong)] bg-[color:var(--color-surface)] text-[color:var(--color-ink)] hover:bg-[color:var(--color-surface-muted)]",
  ghost:
    "border border-transparent bg-transparent text-[color:var(--color-ink)] hover:border-[color:var(--color-border)] hover:bg-white/70",
};

type ButtonVariant = keyof typeof buttonVariants;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({
  className,
  variant = "primary",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-11 items-center justify-center rounded-2xl px-5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60",
        buttonVariants[variant],
        className,
      )}
      type={type}
      {...props}
    />
  );
}
