"use client";

import { useActionState } from "react";

import {
  createTaxonomyEdgeAction,
  createTaxonomyLabelAction,
} from "@/features/taxonomy-controls/actions/taxonomy-controls-actions";
import { initialActionState } from "@/shared/types/action-state";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";

export interface TaxonomyOperationsPanelProps {
  taxonomyId: string;
}

export function TaxonomyOperationsPanel({ taxonomyId }: TaxonomyOperationsPanelProps) {
  const [edgeState, edgeAction, edgePending] = useActionState(
    createTaxonomyEdgeAction.bind(null, taxonomyId),
    initialActionState,
  );
  const [labelState, labelAction, labelPending] = useActionState(
    createTaxonomyLabelAction.bind(null, taxonomyId),
    initialActionState,
  );

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <form
        action={edgeAction}
        className="space-y-4 rounded-[26px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-5"
      >
        <p className="text-base font-semibold text-[color:var(--color-ink)]">Add edge</p>
        <div>
          <Label htmlFor="parentConceptId">Parent concept id</Label>
          <Input id="parentConceptId" name="parentConceptId" />
        </div>
        <div>
          <Label htmlFor="childConceptId">Child concept id</Label>
          <Input id="childConceptId" name="childConceptId" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="relation">Relation</Label>
            <Input id="relation" name="relation" placeholder="broader" />
          </div>
          <div>
            <Label htmlFor="edge-score">Score</Label>
            <Input id="edge-score" name="score" step="0.01" type="number" />
          </div>
        </div>
        {edgeState.message ? (
          <p
            className={
              edgeState.status === "error"
                ? "text-sm text-[color:var(--color-ink)]"
                : "text-sm text-[color:var(--color-muted)]"
            }
          >
            {edgeState.message}
          </p>
        ) : null}
        <Button disabled={edgePending} type="submit">
          {edgePending ? "Creating..." : "Create edge"}
        </Button>
      </form>

      <form
        action={labelAction}
        className="space-y-4 rounded-[26px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-5"
      >
        <p className="text-base font-semibold text-[color:var(--color-ink)]">Create label</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="candidateId">Candidate id</Label>
            <Input id="candidateId" name="candidateId" />
          </div>
          <div>
            <Label htmlFor="reviewerId">Reviewer id</Label>
            <Input id="reviewerId" name="reviewerId" />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="parentLabel">Parent label</Label>
            <Input id="parentLabel" name="parentLabel" />
          </div>
          <div>
            <Label htmlFor="childLabel">Child label</Label>
            <Input id="childLabel" name="childLabel" />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="label">Label</Label>
            <Input id="label" name="label" />
          </div>
          <div>
            <Label htmlFor="labelSource">Label source</Label>
            <Input id="labelSource" name="labelSource" placeholder="manual" />
          </div>
        </div>
        <div>
          <Label htmlFor="reason">Reason</Label>
          <Textarea id="reason" name="reason" rows={3} />
        </div>
        {labelState.message ? (
          <p
            className={
              labelState.status === "error"
                ? "text-sm text-[color:var(--color-ink)]"
                : "text-sm text-[color:var(--color-muted)]"
            }
          >
            {labelState.message}
          </p>
        ) : null}
        <Button disabled={labelPending} type="submit" variant="secondary">
          {labelPending ? "Creating..." : "Create label"}
        </Button>
      </form>
    </div>
  );
}
