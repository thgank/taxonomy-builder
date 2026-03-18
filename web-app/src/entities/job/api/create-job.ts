import type { CreateJobRequest, Job } from "@/entities/job/types/job";
import { backendRequest } from "@/shared/api/backend-client";

export async function createJob(collectionId: string, payload: CreateJobRequest) {
  return backendRequest<Job>(`/api/collections/${collectionId}/jobs`, {
    method: "POST",
    body: payload,
  });
}
