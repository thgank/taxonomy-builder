"use client";

import { useActionState } from "react";

import type { TaxonomyRelease } from "@/entities/release/types/release";
import type { TaxonomyVersion } from "@/entities/taxonomy/types/taxonomy";
import {
  createReleaseAction,
  promoteReleaseAction,
  rollbackReleaseAction,
} from "@/features/release-management/actions/release-actions";
import { initialActionState } from "@/shared/types/action-state";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

export interface ReleaseManagementPanelProps {
  collectionId: string;
  releases: TaxonomyRelease[];
  taxonomyVersions: TaxonomyVersion[];
}

export function ReleaseManagementPanel({
  collectionId,
  releases,
  taxonomyVersions,
}: ReleaseManagementPanelProps) {
  const [state, createAction, isPending] = useActionState(
    createReleaseAction.bind(null, collectionId),
    initialActionState,
  );

  return (
    <div className="space-y-8">
      <form
        action={createAction}
        className="space-y-4 rounded-[26px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-5"
      >
        <p className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
          Create release
        </p>
        <div>
          <Label htmlFor="release-taxonomy-version">Taxonomy version</Label>
          <Select id="release-taxonomy-version" name="taxonomyVersionId">
            <option value="">Select version</option>
            {taxonomyVersions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.algorithm} · {version.id}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="release-name">Release name</Label>
          <Input id="release-name" name="releaseName" placeholder="2026-03 active cut" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="release-channel">Channel</Label>
            <Select id="release-channel" name="channel">
              <option value="active">active</option>
              <option value="canary">canary</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="release-traffic">Traffic percent</Label>
            <Input id="release-traffic" name="trafficPercent" placeholder="100" type="number" />
          </div>
        </div>
        <div>
          <Label htmlFor="release-notes">Notes</Label>
          <Textarea id="release-notes" name="notes" rows={3} />
        </div>
        {state.message ? (
          <p
            className={
              state.status === "error"
                ? "text-sm text-[color:var(--color-ink)]"
                : "text-sm text-[color:var(--color-muted)]"
            }
          >
            {state.message}
          </p>
        ) : null}
        <Button disabled={isPending} type="submit" variant="secondary">
          {isPending ? "Creating..." : "Create release"}
        </Button>
      </form>

      <div className="space-y-4">
        {releases.map((release) => (
          <article
            className="rounded-[26px] border border-[color:var(--color-border)] bg-white/80 p-5"
            key={release.id}
          >
            <p className="text-base font-semibold text-[color:var(--color-ink)]">{release.releaseName}</p>
            <p className="mt-1 text-[11px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
              {release.id}
            </p>

            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              <form
                action={promoteReleaseAction.bind(null, collectionId, release.id)}
                className="space-y-3 rounded-[22px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4"
              >
                <p className="text-sm font-semibold text-[color:var(--color-ink)]">Promote</p>
                <Select defaultValue={release.channel} name="channel">
                  <option value="active">active</option>
                  <option value="canary">canary</option>
                </Select>
                <Input defaultValue={release.trafficPercent ?? 100} name="trafficPercent" type="number" />
                <Textarea defaultValue={release.notes ?? ""} name="notes" rows={2} />
                <Button type="submit">Promote</Button>
              </form>

              <form
                action={rollbackReleaseAction.bind(null, collectionId, release.id)}
                className="space-y-3 rounded-[22px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4"
              >
                <p className="text-sm font-semibold text-[color:var(--color-ink)]">Rollback</p>
                <Select name="rollbackToReleaseId">
                  <option value="">Select release</option>
                  {releases.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.releaseName} · {candidate.id}
                    </option>
                  ))}
                </Select>
                <Select defaultValue={release.channel} name="channel">
                  <option value="active">active</option>
                  <option value="canary">canary</option>
                </Select>
                <Textarea name="notes" rows={2} />
                <Button type="submit" variant="secondary">
                  Rollback
                </Button>
              </form>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
