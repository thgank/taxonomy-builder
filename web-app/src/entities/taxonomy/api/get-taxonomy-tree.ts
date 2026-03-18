import type { TaxonomyTree } from "@/entities/taxonomy/types/taxonomy";
import { backendRequest } from "@/shared/api/backend-client";

export async function getTaxonomyTree(taxonomyId: string) {
  return backendRequest<TaxonomyTree>(`/api/taxonomies/${taxonomyId}/tree`);
}
