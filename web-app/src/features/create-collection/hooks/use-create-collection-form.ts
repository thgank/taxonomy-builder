"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { useForm } from "react-hook-form";

import { createCollectionAction } from "@/features/create-collection/actions/create-collection-action";
import {
  createCollectionSchema,
  type CreateCollectionFormValues,
} from "@/features/create-collection/validators/create-collection-schema";

export function useCreateCollectionForm() {
  const router = useRouter();
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const form = useForm<CreateCollectionFormValues>({
    resolver: zodResolver(createCollectionSchema),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    startTransition(async () => {
      setSubmissionError(null);

      const result = await createCollectionAction(values);

      if (!result.success) {
        if (result.fieldErrors?.name) {
          form.setError("name", { message: result.fieldErrors.name });
        }

        if (result.fieldErrors?.description) {
          form.setError("description", { message: result.fieldErrors.description });
        }

        setSubmissionError(result.message ?? "Failed to create collection.");
        return;
      }

      router.push(`/collections/${result.collectionId}`);
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
