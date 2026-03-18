import Link from "next/link";

import type { Document } from "@/entities/document/types/document";
import { formatDateTime, formatFileSize } from "@/shared/lib/format";
import { EmptyState } from "@/shared/ui/empty-state";
import { StatusBadge } from "@/shared/ui/status-badge";

export interface DocumentListProps {
  documents: Document[];
}

export function DocumentList({ documents }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <EmptyState
        title="No documents in this collection"
        description="Add your first files to begin shaping the collection."
      />
    );
  }

  return (
    <div className="space-y-4">
      {documents.map((document) => (
        <article
          className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
          key={document.id}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <Link href={`/documents/${document.id}`}>
                <h3 className="text-lg font-semibold text-[color:var(--color-ink)]">
                  {document.filename}
                </h3>
              </Link>
              <p className="mt-1 text-sm text-[color:var(--color-muted)]">
                {document.mimeType} · {formatFileSize(document.sizeBytes)}
              </p>
            </div>
            <StatusBadge value={document.status} />
          </div>
          <dl className="mt-5 grid gap-3 text-sm text-[color:var(--color-muted)] sm:grid-cols-2">
            <div className="rounded-[20px] bg-[color:var(--color-surface-muted)] p-3">
              <dt className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Created
              </dt>
              <dd className="mt-1 text-[color:var(--color-ink)]">
                {formatDateTime(document.createdAt)}
              </dd>
            </div>
            <div className="rounded-[20px] bg-[color:var(--color-surface-muted)] p-3">
              <dt className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Parsed
              </dt>
              <dd className="mt-1 text-[color:var(--color-ink)]">
                {formatDateTime(document.parsedAt)}
              </dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}
