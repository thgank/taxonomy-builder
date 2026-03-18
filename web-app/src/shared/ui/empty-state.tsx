import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-[28px] border border-dashed border-[color:var(--color-border-strong)] bg-[color:var(--color-surface-muted)] p-8 text-center">
      <h3 className="text-lg font-semibold text-[color:var(--color-ink)]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[color:var(--color-muted)]">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
