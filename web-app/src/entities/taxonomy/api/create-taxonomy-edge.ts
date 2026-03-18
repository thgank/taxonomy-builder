import type { ApiJsonRequest, ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { toUnknownRecordArray } from "@/shared/lib/records";

import type { TaxonomyEdge } from "../types/taxonomy";

type CreateEdgePayload = ApiJsonRequest<"addEdge">;
type CreateEdgeResponse = ApiResponse<"addEdge", 201>;

export async function createTaxonomyEdge(
  taxonomyId: string,
  payload: CreateEdgePayload,
): Promise<TaxonomyEdge> {
  const response = await backendRequest<CreateEdgeResponse>(`/api/taxonomies/${taxonomyId}/edges`, {
    method: "POST",
    body: payload,
  });

  return {
    id: response.id ?? "",
    parentConceptId: response.parentConceptId ?? payload.parentConceptId,
    parentLabel: response.parentLabel ?? "",
    childConceptId: response.childConceptId ?? payload.childConceptId,
    childLabel: response.childLabel ?? "",
    relation: response.relation ?? null,
    score: response.score ?? null,
    evidence: toUnknownRecordArray(response.evidence),
  };
}
