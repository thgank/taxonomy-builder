import type { ApiJsonRequest, ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { toUnknownRecord } from "@/shared/lib/records";

import type { TaxonomyEdgeLabel } from "../types/taxonomy";

type CreateLabelPayload = ApiJsonRequest<"createEdgeLabel">;
type CreateLabelResponse = ApiResponse<"createEdgeLabel", 201>;

export async function createTaxonomyLabel(
  taxonomyId: string,
  payload: CreateLabelPayload,
): Promise<TaxonomyEdgeLabel> {
  const response = await backendRequest<CreateLabelResponse>(`/api/taxonomies/${taxonomyId}/labels`, {
    method: "POST",
    body: payload,
  });

  return {
    id: response.id ?? "",
    candidateId: response.candidateId ?? null,
    taxonomyVersionId: response.taxonomyVersionId ?? taxonomyId,
    collectionId: response.collectionId ?? "",
    parentConceptId: response.parentConceptId ?? null,
    childConceptId: response.childConceptId ?? null,
    parentLabel: response.parentLabel ?? null,
    childLabel: response.childLabel ?? null,
    label: response.label ?? null,
    labelSource: response.labelSource ?? null,
    reviewerId: response.reviewerId ?? null,
    reason: response.reason ?? null,
    meta: toUnknownRecord(response.meta),
    createdAt: response.createdAt ?? "",
  };
}
