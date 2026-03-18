import type { ApiJsonRequest, ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { toUnknownRecord } from "@/shared/lib/records";

import type { TaxonomyRelease } from "../types/release";

type RollbackReleasePayload = ApiJsonRequest<"rollbackRelease">;
type RollbackReleaseResponse = ApiResponse<"rollbackRelease", 200>;

export async function rollbackRelease(
  collectionId: string,
  releaseId: string,
  payload: RollbackReleasePayload,
): Promise<TaxonomyRelease> {
  const response = await backendRequest<RollbackReleaseResponse>(
    `/api/collections/${collectionId}/releases/${releaseId}/rollback`,
    {
      method: "POST",
      body: payload,
    },
  );

  return {
    id: response.id ?? releaseId,
    collectionId: response.collectionId ?? collectionId,
    taxonomyVersionId: response.taxonomyVersionId ?? "",
    releaseName: response.releaseName ?? "Unnamed release",
    channel: response.channel ?? "active",
    trafficPercent: response.trafficPercent ?? null,
    isActive: response.isActive ?? null,
    rollbackOf: response.rollbackOf ?? null,
    qualitySnapshot: toUnknownRecord(response.qualitySnapshot),
    notes: response.notes ?? null,
    createdAt: response.createdAt ?? "",
  };
}
