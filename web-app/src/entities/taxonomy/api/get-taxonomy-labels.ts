import type { ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { normalizePage, toBackendPageQuery, type Page, type PaginationInput } from "@/shared/lib/pagination";
import { toUnknownRecord } from "@/shared/lib/records";

import type { TaxonomyEdgeLabel } from "../types/taxonomy";

type GetLabelsResponse = ApiResponse<"getEdgeLabels", 200>;

export async function getTaxonomyLabels(
  taxonomyId: string,
  pagination: PaginationInput,
): Promise<Page<TaxonomyEdgeLabel>> {
  const response = await backendRequest<GetLabelsResponse>(`/api/taxonomies/${taxonomyId}/labels`, {
    query: toBackendPageQuery(pagination),
  });

  return normalizePage<TaxonomyEdgeLabel>({
    ...response,
    content: (response.content ?? []).map((label) => ({
      id: label.id ?? "",
      candidateId: label.candidateId ?? null,
      taxonomyVersionId: label.taxonomyVersionId ?? taxonomyId,
      collectionId: label.collectionId ?? "",
      parentConceptId: label.parentConceptId ?? null,
      childConceptId: label.childConceptId ?? null,
      parentLabel: label.parentLabel ?? null,
      childLabel: label.childLabel ?? null,
      label: label.label ?? null,
      labelSource: label.labelSource ?? null,
      reviewerId: label.reviewerId ?? null,
      reason: label.reason ?? null,
      meta: toUnknownRecord(label.meta),
      createdAt: label.createdAt ?? "",
    })),
  });
}
