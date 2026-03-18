"use client";

import { useEffect, useState } from "react";

import { cancelJobAction } from "@/features/pipeline-monitor/actions/cancel-job-action";
import type { JobPipelineSnapshot } from "@/entities/job/types/job";
import { formatDateTime } from "@/shared/lib/format";
import { ProgressBar } from "@/shared/ui/progress-bar";
import { StatusBadge } from "@/shared/ui/status-badge";
import { Button } from "@/shared/ui/button";

export interface PipelineMonitorProps {
  initialSnapshot: JobPipelineSnapshot;
}

export function PipelineMonitor({ initialSnapshot }: PipelineMonitorProps) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);

  useEffect(() => {
    if (!["QUEUED", "RUNNING", "RETRYING"].includes(snapshot.job.status)) {
      return;
    }

    const intervalId = window.setInterval(async () => {
      const response = await fetch(`/api/jobs/${snapshot.job.id}/pipeline`, {
        cache: "no-store",
      });

      if (!response.ok) {
        return;
      }

      const nextSnapshot = (await response.json()) as JobPipelineSnapshot;
      setSnapshot(nextSnapshot);
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [snapshot.job.id, snapshot.job.status]);

  return (
    <div className="space-y-5">
      <div className="rounded-[28px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.24em] text-[color:var(--color-muted-soft)]">
              Pipeline progress
            </p>
            <p className="mt-2 text-[2.2rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
              {snapshot.overallProgress}%
            </p>
          </div>
          <StatusBadge value={snapshot.job.status} />
        </div>
        <ProgressBar className="mt-4" value={snapshot.overallProgress} />
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        {snapshot.stages.map((stage) => (
          <article
            className="rounded-[24px] border border-[color:var(--color-border)] bg-white/80 p-4"
            key={stage.key}
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-base font-semibold text-[color:var(--color-ink)]">{stage.label}</p>
              <StatusBadge value={stage.state.toUpperCase()} />
            </div>
            <ProgressBar className="mt-4" value={stage.progress} />
            <p className="mt-3 text-sm text-[color:var(--color-muted)]">
              {stage.latestMessage ?? "No events yet."}
            </p>
            {stage.latestTimestamp ? (
              <p className="mt-2 text-[11px] uppercase tracking-[0.2em] text-[color:var(--color-muted-soft)]">
                {formatDateTime(stage.latestTimestamp)}
              </p>
            ) : null}
          </article>
        ))}
      </div>

      {["QUEUED", "RUNNING", "RETRYING"].includes(snapshot.job.status) ? (
        <form action={cancelJobAction.bind(null, snapshot.job.id, snapshot.job.collectionId)}>
          <Button type="submit" variant="secondary">
            Cancel job
          </Button>
        </form>
      ) : null}
    </div>
  );
}
