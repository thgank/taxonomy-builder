"use server";

import { revalidatePath } from "next/cache";

import { cancelJob } from "@/entities/job/api/cancel-job";

export async function cancelJobAction(jobId: string, collectionId: string) {
  await cancelJob(jobId);
  revalidatePath(`/jobs/${jobId}`);
  revalidatePath(`/collections/${collectionId}`);
}
