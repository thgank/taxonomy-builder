import Link from "next/link";
import { notFound } from "next/navigation";

import { getDocument } from "@/entities/document/api/get-document";
import { getDocumentChunks } from "@/entities/document/api/get-document-chunks";
import { DocumentChunkList } from "@/entities/document/ui/document-chunk-list";
import { isApiError } from "@/shared/api/error";
import { formatDateTime, formatFileSize } from "@/shared/lib/format";
import { getPaginationFromSearchParams } from "@/shared/lib/pagination";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { PaginationControls } from "@/shared/ui/pagination-controls";
import { SectionHeading } from "@/shared/ui/section-heading";
import { StatusBadge } from "@/shared/ui/status-badge";

function DocumentMetric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <Card className="p-5">
      <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
        {label}
      </p>
      <p className="mt-2 text-[2rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
        {value}
      </p>
    </Card>
  );
}

export default async function DocumentDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ documentId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { documentId } = await params;
  const resolvedSearchParams = await searchParams;
  const pagination = getPaginationFromSearchParams(resolvedSearchParams, { page: 0, size: 20 });
  let documentData: Awaited<ReturnType<typeof getDocument>>;
  let chunksData: Awaited<ReturnType<typeof getDocumentChunks>>;

  try {
    [documentData, chunksData] = await Promise.all([
      getDocument(documentId),
      getDocumentChunks(documentId, pagination),
    ]);
  } catch (error) {
    if (isApiError(error) && error.status === 404) {
      notFound();
    }

    throw error;
  }

  return (
    <div className="space-y-6">
      <section className="hero-panel px-6 py-8 sm:px-8">
        <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
              Document detail
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.06em] text-[color:var(--color-ink)] sm:text-[3.1rem]">
              {documentData.filename}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[color:var(--color-muted)] sm:text-base">
              Review the file details and browse the text segments prepared for taxonomy work.
            </p>
            <p className="mt-5 text-sm text-[color:var(--color-muted)]">
              {documentData.mimeType} · {formatFileSize(documentData.sizeBytes)}
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <div className="metric-card flex items-center justify-between gap-4 p-5">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                  Status
                </p>
                <p className="mt-2 text-lg font-semibold text-[color:var(--color-ink)]">
                  Parse state
                </p>
              </div>
              <StatusBadge value={documentData.status} />
            </div>
            <Link href={`/collections/${documentData.collectionId}`}>
              <Button className="w-full" variant="secondary">
                Back to collection
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <DocumentMetric label="Created" value={formatDateTime(documentData.createdAt)} />
        <DocumentMetric label="Parsed" value={formatDateTime(documentData.parsedAt)} />
        <DocumentMetric label="Chunks on page" value={chunksData.numberOfElements} />
        <DocumentMetric label="Total chunks" value={chunksData.totalElements} />
      </section>

      <Card>
        <SectionHeading
          eyebrow="Chunks"
          title="Document chunk payloads"
          description="Browse the extracted text segments for this document."
        />
        <div className="mt-5">
          <DocumentChunkList chunks={chunksData} />
          <PaginationControls
            page={chunksData}
            pageParam="page"
            pathname={`/documents/${documentData.id}`}
            searchParams={resolvedSearchParams}
          />
        </div>
      </Card>
    </div>
  );
}
