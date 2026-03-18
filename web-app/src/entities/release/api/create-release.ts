import type { ApiJsonRequest, ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { toUnknownRecord } from "@/shared/lib/records";

import type { TaxonomyRelease } from "../types/release";

type CreateReleasePayload = ApiJsonRequest<"createRelease">;
type CreateReleaseResponse = ApiResponse<"createRelease", 201>;

export async function createRelease(
  collectionId: string,
  payload: CreateReleasePayload,
): Promise<TaxonomyRelease> {
  const response = await backendRequest<CreateReleaseResponse>(
    `/api/collections/${collectionId}/releases`,
    {
      method: "POST",
      body: payload,
    },
  );

  return {
    id: response.id ?? "",
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
