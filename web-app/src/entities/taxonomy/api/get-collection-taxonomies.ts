import type { TaxonomyVersion } from "@/entities/taxonomy/types/taxonomy";
import { backendRequest } from "@/shared/api/backend-client";

export async function getCollectionTaxonomies(collectionId: string) {
  return backendRequest<TaxonomyVersion[]>(`/api/collections/${collectionId}/taxonomies`);
}
