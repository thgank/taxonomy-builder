import { backendRequest } from "@/shared/api/backend-client";

export async function deleteTaxonomyEdge(taxonomyId: string, edgeId: string) {
  await backendRequest<void>(`/api/taxonomies/${taxonomyId}/edges/${edgeId}`, {
    method: "DELETE",
  });
}
