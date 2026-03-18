import type { ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";

import type { ConceptDetail } from "../types/taxonomy";

type GetConceptDetailResponse = ApiResponse<"getConceptDetail", 200>;

export async function getConceptDetail(
  taxonomyId: string,
  conceptId: string,
): Promise<ConceptDetail> {
  const response = await backendRequest<GetConceptDetailResponse>(
    `/api/taxonomies/${taxonomyId}/concepts/${conceptId}`,
  );

  return {
    id: response.id ?? conceptId,
    canonical: response.canonical ?? "",
    surfaceForms: response.surfaceForms ?? [],
    lang: response.lang ?? null,
    score: response.score ?? null,
    parents: (response.parents ?? []).map((parent) => ({
      id: parent.id ?? "",
      canonical: parent.canonical ?? "",
      edgeScore: parent.edgeScore ?? null,
    })),
    children: (response.children ?? []).map((child) => ({
      id: child.id ?? "",
      canonical: child.canonical ?? "",
      edgeScore: child.edgeScore ?? null,
    })),
    occurrences: (response.occurrences ?? []).map((occurrence) => ({
      chunkId: occurrence.chunkId ?? "",
      documentId: occurrence.documentId ?? "",
      snippet: occurrence.snippet ?? "",
      confidence: occurrence.confidence ?? null,
    })),
  };
}
