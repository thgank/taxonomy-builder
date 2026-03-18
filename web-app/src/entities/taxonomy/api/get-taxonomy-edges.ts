import type { ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { normalizePage, toBackendPageQuery, type Page, type PaginationInput } from "@/shared/lib/pagination";
import { toUnknownRecordArray } from "@/shared/lib/records";

import type { TaxonomyEdge } from "../types/taxonomy";

type GetEdgesResponse = ApiResponse<"getEdges", 200>;

export async function getTaxonomyEdges(
  taxonomyId: string,
  pagination: PaginationInput,
): Promise<Page<TaxonomyEdge>> {
  const response = await backendRequest<GetEdgesResponse>(`/api/taxonomies/${taxonomyId}/edges`, {
    query: toBackendPageQuery(pagination),
  });

  return normalizePage<TaxonomyEdge>({
    ...response,
    content: (response.content ?? []).map((edge) => ({
      id: edge.id ?? "",
      parentConceptId: edge.parentConceptId ?? "",
      parentLabel: edge.parentLabel ?? "",
      childConceptId: edge.childConceptId ?? "",
      childLabel: edge.childLabel ?? "",
      relation: edge.relation ?? null,
      score: edge.score ?? null,
      evidence: toUnknownRecordArray(edge.evidence),
    })),
  });
}
