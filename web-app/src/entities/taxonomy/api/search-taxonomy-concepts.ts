import type { ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { normalizePage, toBackendPageQuery, type Page, type PaginationInput } from "@/shared/lib/pagination";

import type { Concept } from "../types/taxonomy";

type SearchConceptsResponse = ApiResponse<"searchConcepts", 200>;

export async function searchTaxonomyConcepts(
  taxonomyId: string,
  query: string,
  pagination: PaginationInput,
): Promise<Page<Concept>> {
  const response = await backendRequest<SearchConceptsResponse>(
    `/api/taxonomies/${taxonomyId}/concepts/search`,
    {
      query: {
        q: query,
        ...toBackendPageQuery(pagination),
      },
    },
  );

  return normalizePage<Concept>({
    ...response,
    content: (response.content ?? []).map((concept) => ({
      id: concept.id ?? "",
      canonical: concept.canonical ?? "",
      surfaceForms: concept.surfaceForms ?? [],
      lang: concept.lang ?? null,
      score: concept.score ?? null,
    })),
  });
}
