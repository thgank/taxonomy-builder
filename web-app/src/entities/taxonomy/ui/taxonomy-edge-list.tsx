import { deleteTaxonomyEdgeAction, updateTaxonomyEdgeAction } from "@/features/taxonomy-controls/actions/taxonomy-controls-actions";
import type { Page } from "@/shared/lib/pagination";
import { EmptyState } from "@/shared/ui/empty-state";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";

import type { TaxonomyEdge } from "../types/taxonomy";

export interface TaxonomyEdgeListProps {
  taxonomyId: string;
  edges: Page<TaxonomyEdge>;
}

export function TaxonomyEdgeList({ taxonomyId, edges }: TaxonomyEdgeListProps) {
  if (edges.content.length === 0) {
    return (
      <EmptyState
        title="No edges on this page"
        description="There are no relationship records in this slice of the taxonomy."
      />
    );
  }

  return (
    <div className="space-y-4">
      {edges.content.map((edge) => (
        <article
          className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
          key={edge.id}
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-lg font-semibold text-[color:var(--color-ink)]">
                {edge.parentLabel} → {edge.childLabel}
              </p>
              <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                {edge.id}
              </p>
            </div>
            <p className="text-sm text-[color:var(--color-muted)]">
              {edge.relation || "unspecified"} · score {edge.score?.toFixed(2) ?? "n/a"}
            </p>
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_auto]">
            <form
              action={updateTaxonomyEdgeAction.bind(null, taxonomyId, edge.id)}
              className="grid gap-3 sm:grid-cols-[160px_auto_140px]"
            >
              <Input defaultValue={edge.score ?? undefined} name="score" step="0.01" type="number" />
              <label className="flex items-center gap-2 rounded-[20px] bg-[color:var(--color-surface-muted)] px-4 text-sm text-[color:var(--color-muted)]">
                <input className="h-4 w-4" name="approved" type="checkbox" />
                Mark approved
              </label>
              <Button type="submit" variant="secondary">
                Update edge
              </Button>
            </form>

            <form action={deleteTaxonomyEdgeAction.bind(null, taxonomyId, edge.id)}>
              <Button type="submit">Delete</Button>
            </form>
          </div>
        </article>
      ))}
    </div>
  );
}
