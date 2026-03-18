import Link from "next/link";

import { TaxonomyEdgeList } from "@/entities/taxonomy/ui/taxonomy-edge-list";
import { TaxonomyLabelList } from "@/entities/taxonomy/ui/taxonomy-label-list";
import { TaxonomyTreeView } from "@/entities/taxonomy/ui/taxonomy-tree";
import type {
  Concept,
  ConceptDetail,
  TaxonomyEdge,
  TaxonomyEdgeLabel,
  TaxonomyTree,
  TaxonomyVersion,
} from "@/entities/taxonomy/types/taxonomy";
import { TaxonomyOperationsPanel } from "@/features/taxonomy-controls/components/taxonomy-operations-panel";
import { formatDateTime, formatJsonCompact } from "@/shared/lib/format";
import type { Page } from "@/shared/lib/pagination";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { PaginationControls } from "@/shared/ui/pagination-controls";
import { SectionHeading } from "@/shared/ui/section-heading";
import { StatusBadge } from "@/shared/ui/status-badge";

export interface TaxonomyExplorerProps {
  taxonomyId: string;
  version: TaxonomyVersion;
  tree: TaxonomyTree;
  edges: Page<TaxonomyEdge>;
  labels: Page<TaxonomyEdgeLabel>;
  concepts: Page<Concept> | null;
  selectedConcept: ConceptDetail | null;
  searchQuery: string;
  searchParams: Record<string, string | string[] | undefined>;
}

function TaxonomyMetric({
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

export function TaxonomyExplorer({
  taxonomyId,
  version,
  tree,
  edges,
  labels,
  concepts,
  selectedConcept,
  searchQuery,
  searchParams,
}: TaxonomyExplorerProps) {
  return (
    <div className="space-y-6">
      <section className="hero-panel px-6 py-8 sm:px-8">
        <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
              Taxonomy explorer
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.06em] text-[color:var(--color-ink)] sm:text-[3.1rem]">
              {version.algorithm}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[color:var(--color-muted)] sm:text-base">
              Explore the structure, refine relationships, search concepts, and prepare this
              version for wider use.
            </p>
            <p className="mt-5 text-sm text-[color:var(--color-muted)]">Version id {version.id}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <div className="metric-card flex items-center justify-between gap-4 p-5">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                  Status
                </p>
                <p className="mt-2 text-lg font-semibold text-[color:var(--color-ink)]">
                  Current state
                </p>
              </div>
              <StatusBadge value={version.status} />
            </div>
            <div className="metric-card p-5">
              <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                Tree roots
              </p>
              <p className="mt-2 text-[2rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
                {tree.roots.length}
              </p>
              <p className="mt-2 text-sm text-[color:var(--color-muted)]">
                Starting branches in this version.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <TaxonomyMetric label="Concepts" value={version.conceptCount} />
        <TaxonomyMetric label="Edges" value={version.edgeCount} />
        <TaxonomyMetric label="Created" value={formatDateTime(version.createdAt)} />
        <TaxonomyMetric label="Finished" value={formatDateTime(version.finishedAt)} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <SectionHeading
            eyebrow="Parameters"
            title="Generation configuration"
            description="Saved settings and notes for this version."
          />
          <pre className="mt-5 overflow-x-auto rounded-[24px] bg-[color:var(--color-surface-muted)] p-5 text-xs leading-6 text-[color:var(--color-muted)]">
            {formatJsonCompact(version.parameters)}
          </pre>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Exports"
            title="Output delivery"
            description="Direct links for JSON and CSV export variants."
          />
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <Link href={`/api/taxonomies/${taxonomyId}/export?format=json&include_orphans=false`}>
              <Button className="w-full" variant="secondary">
                Export JSON
              </Button>
            </Link>
            <Link href={`/api/taxonomies/${taxonomyId}/export?format=csv&include_orphans=true`}>
              <Button className="w-full" variant="secondary">
                Export CSV + orphans
              </Button>
            </Link>
          </div>
        </Card>
      </section>

      <Card>
        <SectionHeading
          eyebrow="Tree"
          title="Concept hierarchy"
          description={`Showing ${tree.roots.length} starting branches for this version.`}
        />
        <div className="mt-5">
          <TaxonomyTreeView nodes={tree.roots} />
        </div>
      </Card>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <SectionHeading
            eyebrow="Edges"
            title="Manual edge workbench"
            description="Paginated list for reviewing, updating, and deleting edge records."
          />
          <div className="mt-5">
            <TaxonomyEdgeList edges={edges} taxonomyId={taxonomyId} />
            <PaginationControls
              page={edges}
              pageParam="edgePage"
              pathname={`/taxonomies/${taxonomyId}`}
              searchParams={searchParams}
            />
          </div>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Labels"
            title="Edge labels"
            description="Track naming decisions and manual annotations for relationships."
          />
          <div className="mt-5">
            <TaxonomyLabelList labels={labels} />
            <PaginationControls
              page={labels}
              pageParam="labelPage"
              pathname={`/taxonomies/${taxonomyId}`}
              searchParams={searchParams}
            />
          </div>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <Card>
          <SectionHeading
            eyebrow="Concept Search"
            title="Search concepts"
            description="Find a concept quickly and jump into the branch where it lives."
          />
          <form className="mt-5 flex flex-col gap-3 sm:flex-row" method="get">
            <Input
              className="flex-1"
              defaultValue={searchQuery}
              name="q"
              placeholder="Search canonical concept names"
            />
            <Button type="submit">Search</Button>
          </form>

          <div className="mt-5">
            {!concepts ? (
              <EmptyState
                title="No search yet"
                description="Submit a concept query to load paginated concept results."
              />
            ) : concepts.content.length === 0 ? (
              <EmptyState
                title="No concepts matched"
                description="Nothing matched this query. Try a broader term or a different spelling."
              />
            ) : (
              <div className="space-y-3">
                {concepts.content.map((concept) => (
                  <Link
                    className="block rounded-[22px] border border-[color:var(--color-border)] bg-white/80 p-4 transition hover:border-[color:var(--color-border-strong)]"
                    href={`/taxonomies/${taxonomyId}?q=${encodeURIComponent(searchQuery)}&conceptId=${concept.id}&conceptPage=${concepts.number}`}
                    key={concept.id}
                    scroll={false}
                  >
                    <p className="text-base font-semibold text-[color:var(--color-ink)]">
                      {concept.canonical}
                    </p>
                    <p className="mt-1 text-sm text-[color:var(--color-muted)]">
                      {concept.lang || "unknown"} · score {concept.score?.toFixed(2) ?? "n/a"}
                    </p>
                  </Link>
                ))}
                <PaginationControls
                  page={concepts}
                  pageParam="conceptPage"
                  pathname={`/taxonomies/${taxonomyId}`}
                  searchParams={searchParams}
                />
              </div>
            )}
          </div>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Concept Detail"
            title="Selected concept"
            description="Inspect how this concept fits into the structure around it."
          />
          <div className="mt-5">
            {!selectedConcept ? (
              <EmptyState
                title="No concept selected"
                description="Choose a concept from search results to inspect parents, children, and evidence."
              />
            ) : (
              <div className="space-y-5">
                <div>
                  <p className="text-[1.85rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
                    {selectedConcept.canonical}
                  </p>
                  <p className="mt-2 text-sm text-[color:var(--color-muted)]">
                    {selectedConcept.lang || "unknown"} · score {selectedConcept.score?.toFixed(2) ?? "n/a"}
                  </p>
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[color:var(--color-muted-soft)]">
                      Parents
                    </p>
                    <div className="mt-3 space-y-3">
                      {selectedConcept.parents.map((parent) => (
                        <div
                          className="rounded-[22px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4"
                          key={parent.id}
                        >
                          <p className="font-semibold text-[color:var(--color-ink)]">
                            {parent.canonical}
                          </p>
                          <p className="mt-1 text-sm text-[color:var(--color-muted)]">
                            Score {parent.edgeScore?.toFixed(2) ?? "n/a"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[color:var(--color-muted-soft)]">
                      Children
                    </p>
                    <div className="mt-3 space-y-3">
                      {selectedConcept.children.map((child) => (
                        <div
                          className="rounded-[22px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4"
                          key={child.id}
                        >
                          <p className="font-semibold text-[color:var(--color-ink)]">
                            {child.canonical}
                          </p>
                          <p className="mt-1 text-sm text-[color:var(--color-muted)]">
                            Score {child.edgeScore?.toFixed(2) ?? "n/a"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[color:var(--color-muted-soft)]">
                    Evidence
                  </p>
                  <div className="mt-3 space-y-3">
                    {selectedConcept.occurrences.map((occurrence) => (
                      <article
                        className="rounded-[22px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4"
                        key={`${occurrence.chunkId}-${occurrence.documentId}`}
                      >
                        <p className="text-sm leading-6 text-[color:var(--color-ink)]">
                          {occurrence.snippet}
                        </p>
                        <p className="mt-3 text-[11px] uppercase tracking-[0.2em] text-[color:var(--color-muted-soft)]">
                          confidence {occurrence.confidence?.toFixed(2) ?? "n/a"} · document {occurrence.documentId}
                        </p>
                      </article>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}
