import type { JobEvent } from "@/entities/job/types/job";
import { backendRequest } from "@/shared/api/backend-client";

export async function getJobEvents(jobId: string) {
  return backendRequest<JobEvent[]>(`/api/jobs/${jobId}/events`);
}
