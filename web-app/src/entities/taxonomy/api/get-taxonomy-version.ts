import type { TaxonomyVersion } from "@/entities/taxonomy/types/taxonomy";
import { backendRequest } from "@/shared/api/backend-client";

export async function getTaxonomyVersion(taxonomyId: string) {
  return backendRequest<TaxonomyVersion>(`/api/taxonomies/${taxonomyId}`);
}
