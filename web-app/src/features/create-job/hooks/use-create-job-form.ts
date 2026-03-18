"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { useForm } from "react-hook-form";

import { createJobAction } from "@/features/create-job/actions/create-job-action";
import {
  createJobSchema,
  type CreateJobFormValues,
} from "@/features/create-job/validators/create-job-schema";

export function useCreateJobForm(collectionId: string) {
  const router = useRouter();
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const form = useForm<CreateJobFormValues>({
    resolver: zodResolver(createJobSchema),
    defaultValues: {
      type: "FULL_PIPELINE",
      paramsText: "{}",
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    startTransition(async () => {
      setSubmissionError(null);

      const result = await createJobAction(collectionId, values);

      if (!result.success) {
        if (result.fieldErrors?.type) {
          form.setError("type", { message: result.fieldErrors.type });
        }

        if (result.fieldErrors?.paramsText) {
          form.setError("paramsText", { message: result.fieldErrors.paramsText });
        }

        setSubmissionError(result.message ?? "Failed to create job.");
        return;
      }

      router.push(`/jobs/${result.jobId}`);
      router.refresh();
    });
  });

  return {
    form,
    isPending,
    submissionError,
    onSubmit,
  };
}
