import type { Page } from "@/shared/lib/pagination";
import { EmptyState } from "@/shared/ui/empty-state";
import { formatDateTime } from "@/shared/lib/format";

import type { TaxonomyEdgeLabel } from "../types/taxonomy";

export interface TaxonomyLabelListProps {
  labels: Page<TaxonomyEdgeLabel>;
}

export function TaxonomyLabelList({ labels }: TaxonomyLabelListProps) {
  if (labels.content.length === 0) {
    return (
      <EmptyState
        title="No labels on this page"
        description="Manual edge labels will appear here after creation."
      />
    );
  }

  return (
    <div className="space-y-4">
      {labels.content.map((label) => (
        <article
          className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
          key={label.id}
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-lg font-semibold text-[color:var(--color-ink)]">
                {label.parentLabel || "Unknown parent"} → {label.childLabel || "Unknown child"}
              </p>
              <p className="mt-1 text-sm text-[color:var(--color-muted)]">
                Label: {label.label || "n/a"} · source {label.labelSource || "manual"}
              </p>
            </div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
              {formatDateTime(label.createdAt)}
            </p>
          </div>
          {label.reason ? (
            <p className="mt-3 text-sm leading-6 text-[color:var(--color-muted)]">{label.reason}</p>
          ) : null}
        </article>
      ))}
    </div>
  );
}
