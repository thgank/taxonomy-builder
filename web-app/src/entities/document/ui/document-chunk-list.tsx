import type { Page } from "@/shared/lib/pagination";
import { EmptyState } from "@/shared/ui/empty-state";

import type { DocumentChunk } from "../types/document";

export interface DocumentChunkListProps {
  chunks: Page<DocumentChunk>;
}

export function DocumentChunkList({ chunks }: DocumentChunkListProps) {
  if (chunks.content.length === 0) {
    return (
      <EmptyState
        title="No chunks available"
        description="No extracted text segments are available for this document yet."
      />
    );
  }

  return (
    <div className="space-y-4">
      {chunks.content.map((chunk) => (
        <article
          className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
          key={chunk.id}
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-lg font-semibold text-[color:var(--color-ink)]">
                Chunk #{chunk.chunkIndex}
              </p>
              <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                {chunk.id}
              </p>
            </div>
            <p className="text-sm text-[color:var(--color-muted)]">
              {chunk.lang || "unknown"} · chars {chunk.charStart ?? 0} - {chunk.charEnd ?? 0}
            </p>
          </div>
          <p className="mt-4 whitespace-pre-wrap rounded-[20px] bg-[color:var(--color-surface-muted)] p-4 text-sm leading-7 text-[color:var(--color-ink)]">
            {chunk.text}
          </p>
        </article>
      ))}
    </div>
  );
}
