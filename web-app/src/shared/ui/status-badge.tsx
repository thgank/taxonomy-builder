import { Badge } from "@/shared/ui/badge";

const statusStyles: Record<string, string> = {
  NEW: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.05)] text-[color:var(--color-ink)]",
  QUEUED: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.05)] text-[color:var(--color-ink)]",
  RUNNING: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.08)] text-[color:var(--color-ink)]",
  RETRYING: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.08)] text-[color:var(--color-ink)]",
  READY: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.11)] text-[color:var(--color-ink)]",
  SUCCESS: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.11)] text-[color:var(--color-ink)]",
  COMPLETED: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.11)] text-[color:var(--color-ink)]",
  PARSED: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.11)] text-[color:var(--color-ink)]",
  FAILED: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.14)] text-[color:var(--color-ink)]",
  CANCELLED: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.14)] text-[color:var(--color-ink)]",
  PENDING: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.06)] text-[color:var(--color-ink)]",
  active: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.11)] text-[color:var(--color-ink)]",
  canary: "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.08)] text-[color:var(--color-ink)]",
};

export interface StatusBadgeProps {
  value: string | null | undefined;
}

export function StatusBadge({ value }: StatusBadgeProps) {
  const label = value ?? "UNKNOWN";
  const className =
    statusStyles[label] ??
    "border-[color:var(--color-border)] bg-[color:rgba(17,17,17,0.06)] text-[color:var(--color-ink)]";

  return <Badge className={className}>{label}</Badge>;
}
