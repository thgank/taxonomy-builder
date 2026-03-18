"use client";

import { useCreateCollectionForm } from "@/features/create-collection/hooks/use-create-collection-form";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";

export function CreateCollectionForm() {
  const { form, isPending, onSubmit, submissionError } = useCreateCollectionForm();

  return (
    <Card className="h-full bg-[color:var(--color-surface-muted)]">
      <div className="mb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[color:var(--color-accent)]">
          New Collection
        </p>
        <h2 className="mt-3 text-[1.9rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
          Start a new workspace
        </h2>
        <p className="mt-2 text-sm leading-6 text-[color:var(--color-muted)]">
          Start a space for a specific domain, dataset, or initiative and grow a taxonomy around
          it.
        </p>
      </div>

      <form className="space-y-5" onSubmit={onSubmit}>
        <div>
          <Label htmlFor="collection-name">Name</Label>
          <Input
            id="collection-name"
            placeholder="Energy taxonomy corpus"
            {...form.register("name")}
          />
          {form.formState.errors.name ? (
            <p className="mt-2 text-sm text-[color:var(--color-ink)]">
              {form.formState.errors.name.message}
            </p>
          ) : null}
        </div>

        <div>
          <Label htmlFor="collection-description">Description</Label>
          <Textarea
            id="collection-description"
            placeholder="Operational notes, data scope, and collection intent."
            {...form.register("description")}
          />
          {form.formState.errors.description ? (
            <p className="mt-2 text-sm text-[color:var(--color-ink)]">
              {form.formState.errors.description.message}
            </p>
          ) : null}
        </div>

        {submissionError ? (
          <p className="text-sm text-[color:var(--color-ink)]">{submissionError}</p>
        ) : null}

        <Button className="w-full sm:w-auto" disabled={isPending} type="submit">
          {isPending ? "Creating..." : "Create collection"}
        </Button>
      </form>
    </Card>
  );
}
