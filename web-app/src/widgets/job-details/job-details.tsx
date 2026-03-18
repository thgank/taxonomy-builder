import Link from "next/link";

import type { JobPipelineSnapshot } from "@/entities/job/types/job";
import { PipelineMonitor } from "@/features/pipeline-monitor/components/pipeline-monitor";
import { formatDateTime, formatJsonCompact } from "@/shared/lib/format";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { SectionHeading } from "@/shared/ui/section-heading";
import { StatusBadge } from "@/shared/ui/status-badge";

export interface JobDetailsProps {
  snapshot: JobPipelineSnapshot;
}

function JobMetric({
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

export function JobDetails({ snapshot }: JobDetailsProps) {
  const { job, events } = snapshot;

  return (
    <div className="space-y-6">
      <section className="hero-panel px-6 py-8 sm:px-8">
        <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
              Job monitor
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.06em] text-[color:var(--color-ink)] sm:text-[3.1rem]">
              {job.type}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[color:var(--color-muted)] sm:text-base">
              Follow this run as it moves forward, watch for blockers, and keep work on track.
            </p>
            <p className="mt-5 text-sm text-[color:var(--color-muted)]">Job id {job.id}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <div className="metric-card flex items-center justify-between gap-4 p-5">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                  Status
                </p>
                <p className="mt-2 text-lg font-semibold text-[color:var(--color-ink)]">
                  Execution state
                </p>
              </div>
              <StatusBadge value={job.status} />
            </div>
            {job.collectionId ? (
              <Link href={`/collections/${job.collectionId}`}>
                <Button className="w-full" variant="secondary">
                  Back to collection
                </Button>
              </Link>
            ) : null}
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <JobMetric label="Progress" value={`${job.progress}%`} />
        <JobMetric label="Created" value={formatDateTime(job.createdAt)} />
        <JobMetric label="Started" value={formatDateTime(job.startedAt)} />
        <JobMetric label="Finished" value={formatDateTime(job.finishedAt)} />
      </section>

      <PipelineMonitor initialSnapshot={snapshot} />

      {job.errorMessage ? (
        <Card className="border-[color:var(--color-border-strong)] bg-[color:var(--color-surface-muted)]">
          <SectionHeading
            eyebrow="Failure"
            title="This run needs attention"
            description={job.errorMessage}
          />
        </Card>
      ) : null}

      <Card>
        <SectionHeading
          eyebrow="Audit Trail"
          title="Run timeline"
          description="A step-by-step record of what happened during this run."
        />
        <div className="mt-5">
          {events.length === 0 ? (
            <EmptyState
              title="No events recorded"
              description="This run has started, but there is no timeline activity yet."
            />
          ) : (
            <div className="space-y-4">
              {events.map((event) => (
                <article
                  className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
                  key={event.id}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-lg font-semibold text-[color:var(--color-ink)]">
                        {event.message}
                      </p>
                      <p className="mt-1 text-sm text-[color:var(--color-muted)]">
                        {event.level} · {formatDateTime(event.ts)}
                      </p>
                    </div>
                  </div>
                  {event.meta && Object.keys(event.meta).length > 0 ? (
                    <pre className="mt-4 overflow-x-auto rounded-[20px] bg-[color:var(--color-surface-muted)] p-4 text-xs leading-6 text-[color:var(--color-muted)]">
                      {formatJsonCompact(event.meta)}
                    </pre>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
