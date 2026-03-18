"use server";

import { revalidatePath } from "next/cache";

import { createJob } from "@/entities/job/api/create-job";
import type { CreateJobFormValues } from "@/features/create-job/validators/create-job-schema";
import {
  createJobSchema,
  parseJobParams,
} from "@/features/create-job/validators/create-job-schema";
import { isApiError } from "@/shared/api/error";

export interface CreateJobActionResult {
  success: boolean;
  jobId?: string;
  message?: string;
  fieldErrors?: Partial<Record<keyof CreateJobFormValues, string>>;
}

export async function createJobAction(
  collectionId: string,
  input: CreateJobFormValues,
): Promise<CreateJobActionResult> {
  const parsed = createJobSchema.safeParse(input);

  if (!parsed.success) {
    return {
      success: false,
      fieldErrors: {
        type: parsed.error.flatten().fieldErrors.type?.[0],
        paramsText: parsed.error.flatten().fieldErrors.paramsText?.[0],
      },
      message: "Please correct the job configuration before submitting.",
    };
  }

  try {
    const job = await createJob(collectionId, {
      type: parsed.data.type,
      params: parseJobParams(parsed.data.paramsText),
    });

    revalidatePath(`/collections/${collectionId}`);

    return {
      success: true,
      jobId: job.id,
    };
  } catch (error) {
    return {
      success: false,
      message: isApiError(error) ? error.message : "Failed to create processing job.",
    };
  }
}
