import type { Collection } from "@/entities/collection/types/collection";
import { backendRequest } from "@/shared/api/backend-client";

export async function getCollection(collectionId: string) {
  return backendRequest<Collection>(`/api/collections/${collectionId}`);
}
