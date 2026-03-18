import type { Collection } from "@/entities/collection/types/collection";
import { DocumentList } from "@/entities/document/ui/document-list";
import type { Document } from "@/entities/document/types/document";
import { ReleaseList } from "@/entities/release/ui/release-list";
import type { TaxonomyRelease } from "@/entities/release/types/release";
import { TaxonomyVersionList } from "@/entities/taxonomy/ui/taxonomy-version-list";
import type { TaxonomyVersion } from "@/entities/taxonomy/types/taxonomy";
import { CreateJobForm } from "@/features/create-job/components/create-job-form";
import { ReleaseManagementPanel } from "@/features/release-management/components/release-management-panel";
import { UploadDocumentsForm } from "@/features/upload-documents/components/upload-documents-form";
import { formatDateTime, pluralize } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";
import { SectionHeading } from "@/shared/ui/section-heading";

export interface CollectionOverviewProps {
  collection: Collection;
  documents: Document[];
  taxonomyVersions: TaxonomyVersion[];
  releases: TaxonomyRelease[];
}

function CollectionStat({
  label,
  value,
}: {
  label: string;
  value: string;
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

export function CollectionOverview({
  collection,
  documents,
  taxonomyVersions,
  releases,
}: CollectionOverviewProps) {
  return (
    <div className="space-y-6">
      <section className="hero-panel px-6 py-8 sm:px-8">
        <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
              Collection workspace
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.06em] text-[color:var(--color-ink)] sm:text-[3.1rem]">
              {collection.name}
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-[color:var(--color-muted)] sm:text-base">
              {collection.description || "No description provided for this collection."}
            </p>
            <p className="mt-5 text-sm text-[color:var(--color-muted)]">
              Created {formatDateTime(collection.createdAt)}
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            <CollectionStat
              label="Documents"
              value={pluralize(collection.documentCount, "document", "documents")}
            />
            <CollectionStat
              label="Taxonomy versions"
              value={pluralize(taxonomyVersions.length, "version", "versions")}
            />
            <CollectionStat
              label="Releases"
              value={pluralize(releases.length, "release", "releases")}
            />
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <SectionHeading
            eyebrow="Documents"
            title="Document intake"
            description="Bring source files into this collection and keep them ready for exploration."
          />
          <div className="mt-5">
            <UploadDocumentsForm collectionId={collection.id} />
          </div>
          <div className="mt-5">
            <DocumentList documents={documents} />
          </div>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Pipeline"
            title="Run pipeline job"
            description="Launch a fresh run to turn the current material into a new taxonomy version."
          />
          <div className="mt-5">
            <CreateJobForm collectionId={collection.id} />
          </div>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <SectionHeading
            eyebrow="Taxonomies"
            title="Generated versions"
            description="Version metadata, counts, timestamps, parameters, and tree navigation."
          />
          <div className="mt-5">
            <TaxonomyVersionList versions={taxonomyVersions} />
          </div>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Releases"
            title="Release operations"
            description="Prepare the version that should be shared, promoted, or rolled back."
          />
          <div className="mt-5">
            <ReleaseList releases={releases} />
          </div>
          <div className="mt-5">
            <ReleaseManagementPanel
              collectionId={collection.id}
              releases={releases}
              taxonomyVersions={taxonomyVersions}
            />
          </div>
        </Card>
      </section>
    </div>
  );
}
