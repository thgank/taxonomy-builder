import type { ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";
import { normalizePage, toBackendPageQuery, type Page, type PaginationInput } from "@/shared/lib/pagination";

import type { DocumentChunk } from "../types/document";

type GetChunksResponse = ApiResponse<"getChunks", 200>;

export async function getDocumentChunks(
  documentId: string,
  pagination: PaginationInput,
): Promise<Page<DocumentChunk>> {
  const response = await backendRequest<GetChunksResponse>(`/api/documents/${documentId}/chunks`, {
    query: toBackendPageQuery(pagination),
  });

  return normalizePage<DocumentChunk>({
    ...response,
    content: (response.content ?? []).map((chunk) => ({
      id: chunk.id ?? "",
      documentId: chunk.documentId ?? documentId,
      chunkIndex: chunk.chunkIndex ?? 0,
      text: chunk.text ?? "",
      lang: chunk.lang ?? null,
      charStart: chunk.charStart ?? null,
      charEnd: chunk.charEnd ?? null,
    })),
  });
}
