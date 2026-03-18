"use client";

import { jobTypes } from "@/entities/job/types/job";
import { useCreateJobForm } from "@/features/create-job/hooks/use-create-job-form";
import { Button } from "@/shared/ui/button";
import { Label } from "@/shared/ui/label";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

export interface CreateJobFormProps {
  collectionId: string;
}

export function CreateJobForm({ collectionId }: CreateJobFormProps) {
  const { form, isPending, onSubmit, submissionError } = useCreateJobForm(collectionId);

  return (
    <form className="space-y-5" onSubmit={onSubmit}>
      <div>
        <Label htmlFor="job-type">Job type</Label>
        <Select id="job-type" {...form.register("type")}>
          {jobTypes.map((jobType) => (
            <option key={jobType} value={jobType}>
              {jobType}
            </option>
          ))}
        </Select>
        {form.formState.errors.type ? (
          <p className="mt-2 text-sm text-[color:var(--color-ink)]">
            {form.formState.errors.type.message}
          </p>
        ) : null}
      </div>

      <div>
        <Label htmlFor="job-params">Params JSON</Label>
        <Textarea id="job-params" rows={6} {...form.register("paramsText")} />
        {form.formState.errors.paramsText ? (
          <p className="mt-2 text-sm text-[color:var(--color-ink)]">
            {form.formState.errors.paramsText.message}
          </p>
        ) : null}
      </div>

      {submissionError ? (
        <p className="text-sm text-[color:var(--color-ink)]">{submissionError}</p>
      ) : null}

      <Button disabled={isPending} type="submit">
        {isPending ? "Creating job..." : "Start job"}
      </Button>
    </form>
  );
}
