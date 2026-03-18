import type { Job } from "@/entities/job/types/job";
import { backendRequest } from "@/shared/api/backend-client";

export async function getJob(jobId: string) {
  return backendRequest<Job>(`/api/jobs/${jobId}`);
}
