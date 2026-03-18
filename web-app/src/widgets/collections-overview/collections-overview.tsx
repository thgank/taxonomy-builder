import type { Collection } from "@/entities/collection/types/collection";
import { CollectionCard } from "@/entities/collection/ui/collection-card";
import { CreateCollectionForm } from "@/features/create-collection/components/create-collection-form";
import { EmptyState } from "@/shared/ui/empty-state";
import { SectionHeading } from "@/shared/ui/section-heading";

export interface CollectionsOverviewProps {
  collections: Collection[];
}

export function CollectionsOverview({ collections }: CollectionsOverviewProps) {
  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.5fr_0.9fr]">
        <div className="hero-panel px-6 py-8 sm:px-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
            Overview
          </p>
          <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-[-0.06em] text-[color:var(--color-ink)] sm:text-[3.25rem]">
                Build clear, usable taxonomies from well-organized collections.
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-[color:var(--color-muted)] sm:text-base">
                Each collection holds the source material, the working runs, and the versions your
                team wants to review or ship.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
              <div className="metric-card p-5">
                <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                  Collections
                </p>
                <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
                  {collections.length}
                </p>
                <p className="mt-2 text-sm text-[color:var(--color-muted)]">
                  Active spaces for different domains, research tracks, or product areas.
                </p>
              </div>
              <div className="metric-card p-5">
                <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                  Workflow
                </p>
                <p className="mt-3 text-lg font-semibold text-[color:var(--color-ink)]">
                  Focused and steady
                </p>
                <p className="mt-2 text-sm text-[color:var(--color-muted)]">
                  Fewer distractions, clearer branches, and faster navigation across the work.
                </p>
              </div>
            </div>
          </div>
        </div>
        <CreateCollectionForm />
      </section>

      <section className="space-y-5">
        <SectionHeading
          eyebrow="Collections"
          title="Your collections"
          description="Pick the space you want to review, update, or grow into the next taxonomy version."
        />
        {collections.length === 0 ? (
          <EmptyState
            title="No collections yet"
            description="Create the first collection to gather source material and start shaping your taxonomy."
          />
        ) : (
          <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
            {collections.map((collection) => (
              <CollectionCard collection={collection} key={collection.id} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
