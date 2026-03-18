import { cn } from "@/shared/lib/cn";

export interface ProgressBarProps {
  value: number;
  className?: string;
}

export function ProgressBar({ value, className }: ProgressBarProps) {
  const bounded = Math.max(0, Math.min(100, value));

  return (
    <div
      className={cn(
        "h-2.5 w-full rounded-full bg-[color:rgba(23,23,23,0.08)]",
        className,
      )}
    >
      <div
        className="h-full rounded-full bg-[color:var(--color-ink)] transition-[width]"
        style={{ width: `${bounded}%` }}
      />
    </div>
  );
}
