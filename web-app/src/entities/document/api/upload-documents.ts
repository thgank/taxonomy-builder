import { backendRequest } from "@/shared/api/backend-client";
import type { ApiResponse } from "@/shared/api/openapi";

import type { Document } from "../types/document";

type UploadDocumentsResponse = ApiResponse<"upload", 201>;

export async function uploadCollectionDocuments(
  collectionId: string,
  files: File[],
): Promise<Document[]> {
  const formData = new FormData();

  for (const file of files) {
    formData.append("files", file);
  }

  const response = await backendRequest<UploadDocumentsResponse>(
    `/api/collections/${collectionId}/documents:upload`,
    {
      method: "POST",
      body: formData,
    },
  );

  return response.map((document) => ({
    id: document.id ?? "",
    collectionId: document.collectionId ?? collectionId,
    filename: document.filename ?? "Untitled document",
    mimeType: document.mimeType ?? "application/octet-stream",
    sizeBytes: document.sizeBytes ?? null,
    status: (document.status as Document["status"] | undefined) ?? "NEW",
    createdAt: document.createdAt ?? "",
    parsedAt: document.parsedAt ?? null,
  }));
}
