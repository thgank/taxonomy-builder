import Link from "next/link";

import type { TaxonomyVersion } from "@/entities/taxonomy/types/taxonomy";
import { formatDateTime, formatJsonCompact } from "@/shared/lib/format";
import { EmptyState } from "@/shared/ui/empty-state";
import { StatusBadge } from "@/shared/ui/status-badge";

export interface TaxonomyVersionListProps {
  versions: TaxonomyVersion[];
}

export function TaxonomyVersionList({ versions }: TaxonomyVersionListProps) {
  if (versions.length === 0) {
    return (
      <EmptyState
        title="No taxonomy versions yet"
        description="Start a run when you are ready to turn this collection into a browsable structure."
      />
    );
  }

  return (
    <div className="space-y-4">
      {versions.map((version) => (
        <article
          className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
          key={version.id}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-[color:var(--color-ink)]">
                  {version.algorithm}
                </h3>
                <StatusBadge value={version.status} />
              </div>
              <p className="mt-2 text-sm text-[color:var(--color-muted)]">
                {version.conceptCount} concepts · {version.edgeCount} edges
              </p>
            </div>
            <Link
              className="text-sm font-semibold text-[color:var(--color-accent)]"
              href={`/taxonomies/${version.id}`}
            >
              Open tree
            </Link>
          </div>
          <dl className="mt-4 grid gap-3 text-sm text-[color:var(--color-muted)] sm:grid-cols-2">
            <div className="rounded-[20px] bg-[color:var(--color-surface-muted)] p-3">
              <dt className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Created
              </dt>
              <dd className="mt-1 text-[color:var(--color-ink)]">
                {formatDateTime(version.createdAt)}
              </dd>
            </div>
            <div className="rounded-[20px] bg-[color:var(--color-surface-muted)] p-3">
              <dt className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Finished
              </dt>
              <dd className="mt-1 text-[color:var(--color-ink)]">
                {formatDateTime(version.finishedAt)}
              </dd>
            </div>
          </dl>
          <pre className="mt-4 overflow-x-auto rounded-[20px] bg-[color:var(--color-surface-muted)] p-4 text-xs leading-6 text-[color:var(--color-muted)]">
            {formatJsonCompact(version.parameters)}
          </pre>
        </article>
      ))}
    </div>
  );
}
