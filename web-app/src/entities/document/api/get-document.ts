import type { ApiResponse } from "@/shared/api/openapi";
import { backendRequest } from "@/shared/api/backend-client";

import type { Document } from "../types/document";

type GetDocumentResponse = ApiResponse<"get_1", 200>;

export async function getDocument(documentId: string): Promise<Document> {
  const response = await backendRequest<GetDocumentResponse>(`/api/documents/${documentId}`);

  return {
    id: response.id ?? documentId,
    collectionId: response.collectionId ?? "",
    filename: response.filename ?? "Untitled document",
    mimeType: response.mimeType ?? "application/octet-stream",
    sizeBytes: response.sizeBytes ?? null,
    status: (response.status as Document["status"] | undefined) ?? "NEW",
    createdAt: response.createdAt ?? "",
    parsedAt: response.parsedAt ?? null,
  };
}
