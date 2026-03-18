import type { ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";

import type { Job } from "../types/job";

type CancelJobResponse = ApiResponse<"cancel", 200>;

export async function cancelJob(jobId: string): Promise<Job> {
  const response = await backendRequest<CancelJobResponse>(`/api/jobs/${jobId}:cancel`, {
    method: "POST",
  });

  return {
    id: response.id ?? jobId,
    collectionId: response.collectionId ?? "",
    taxonomyVersionId: response.taxonomyVersionId ?? null,
    type: (response.type as Job["type"] | undefined) ?? "FULL_PIPELINE",
    status: (response.status as Job["status"] | undefined) ?? "CANCELLED",
    progress: response.progress ?? 0,
    errorMessage: response.errorMessage ?? null,
    createdAt: response.createdAt ?? "",
    startedAt: response.startedAt ?? null,
    finishedAt: response.finishedAt ?? null,
  };
}
