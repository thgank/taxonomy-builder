import type { ApiJsonRequest, ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { toUnknownRecordArray } from "@/shared/lib/records";

import type { TaxonomyEdge } from "../types/taxonomy";

type UpdateEdgePayload = ApiJsonRequest<"updateEdge">;
type UpdateEdgeResponse = ApiResponse<"updateEdge", 200>;

export async function updateTaxonomyEdge(
  taxonomyId: string,
  edgeId: string,
  payload: UpdateEdgePayload,
): Promise<TaxonomyEdge> {
  const response = await backendRequest<UpdateEdgeResponse>(
    `/api/taxonomies/${taxonomyId}/edges/${edgeId}`,
    {
      method: "PATCH",
      body: payload,
    },
  );

  return {
    id: response.id ?? edgeId,
    parentConceptId: response.parentConceptId ?? "",
    parentLabel: response.parentLabel ?? "",
    childConceptId: response.childConceptId ?? "",
    childLabel: response.childLabel ?? "",
    relation: response.relation ?? null,
    score: response.score ?? null,
    evidence: toUnknownRecordArray(response.evidence),
  };
}
