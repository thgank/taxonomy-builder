import Link from "next/link";

import type { Collection } from "@/entities/collection/types/collection";
import { formatDateTime, pluralize } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";

export interface CollectionCardProps {
  collection: Collection;
}

export function CollectionCard({ collection }: CollectionCardProps) {
  return (
    <Link href={`/collections/${collection.id}`}>
      <Card className="h-full transition hover:-translate-y-0.5 hover:border-[color:var(--color-border-strong)] hover:bg-white/90">
        <div className="flex h-full flex-col justify-between gap-6">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[color:var(--color-accent)]">
              Collection
            </p>
            <h3 className="mt-3 text-[1.65rem] font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {collection.name}
            </h3>
            <p className="mt-3 text-sm leading-6 text-[color:var(--color-muted)]">
              {collection.description || "No description provided."}
            </p>
          </div>
          <div className="grid gap-4 text-sm text-[color:var(--color-muted)] sm:grid-cols-2">
            <div className="rounded-[22px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Documents
              </p>
              <p className="mt-1 text-lg font-semibold text-[color:var(--color-ink)]">
                {pluralize(collection.documentCount, "document", "documents")}
              </p>
            </div>
            <div className="rounded-[22px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Created
              </p>
              <p className="mt-1 text-lg font-semibold text-[color:var(--color-ink)]">
                {formatDateTime(collection.createdAt)}
              </p>
            </div>
          </div>
        </div>
      </Card>
    </Link>
  );
}
