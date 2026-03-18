import type { TaxonomyRelease } from "@/entities/release/types/release";
import { formatDateTime } from "@/shared/lib/format";
import { EmptyState } from "@/shared/ui/empty-state";
import { StatusBadge } from "@/shared/ui/status-badge";

export interface ReleaseListProps {
  releases: TaxonomyRelease[];
}

export function ReleaseList({ releases }: ReleaseListProps) {
  if (releases.length === 0) {
    return (
      <EmptyState
        title="No releases published"
        description="When a version is ready to share, its release history will appear here."
      />
    );
  }

  return (
    <div className="space-y-4">
      {releases.map((release) => (
        <article
          className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
          key={release.id}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-[color:var(--color-ink)]">
                  {release.releaseName}
                </h3>
                <StatusBadge value={release.channel} />
              </div>
              <p className="mt-2 text-sm text-[color:var(--color-muted)]">
                Taxonomy version {release.taxonomyVersionId}
              </p>
            </div>
            {release.isActive ? (
              <span className="text-sm font-semibold text-[color:var(--color-ink)]">Active</span>
            ) : null}
          </div>
          <dl className="mt-4 grid gap-3 text-sm text-[color:var(--color-muted)] sm:grid-cols-2">
            <div className="rounded-[20px] bg-[color:var(--color-surface-muted)] p-3">
              <dt className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Traffic
              </dt>
              <dd className="mt-1 text-[color:var(--color-ink)]">
                {release.trafficPercent ?? 0}%
              </dd>
            </div>
            <div className="rounded-[20px] bg-[color:var(--color-surface-muted)] p-3">
              <dt className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Created
              </dt>
              <dd className="mt-1 text-[color:var(--color-ink)]">
                {formatDateTime(release.createdAt)}
              </dd>
            </div>
          </dl>
          {release.notes ? (
            <p className="mt-4 text-sm leading-6 text-[color:var(--color-muted)]">
              {release.notes}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}
