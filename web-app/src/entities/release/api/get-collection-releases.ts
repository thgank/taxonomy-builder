import type { TaxonomyRelease } from "@/entities/release/types/release";
import { backendRequest } from "@/shared/api/backend-client";

export async function getCollectionReleases(collectionId: string) {
  return backendRequest<TaxonomyRelease[]>(`/api/collections/${collectionId}/releases`);
}
