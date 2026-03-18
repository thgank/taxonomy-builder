import type { Document } from "@/entities/document/types/document";
import { backendRequest } from "@/shared/api/backend-client";

export async function getCollectionDocuments(collectionId: string) {
  return backendRequest<Document[]>(`/api/collections/${collectionId}/documents`);
}
