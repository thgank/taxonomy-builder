import type { ApiJsonRequest, ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { toUnknownRecord } from "@/shared/lib/records";

import type { TaxonomyRelease } from "../types/release";

type PromoteReleasePayload = ApiJsonRequest<"promoteRelease">;
type PromoteReleaseResponse = ApiResponse<"promoteRelease", 200>;

export async function promoteRelease(
  collectionId: string,
  releaseId: string,
  payload: PromoteReleasePayload,
): Promise<TaxonomyRelease> {
  const response = await backendRequest<PromoteReleaseResponse>(
    `/api/collections/${collectionId}/releases/${releaseId}/promote`,
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
