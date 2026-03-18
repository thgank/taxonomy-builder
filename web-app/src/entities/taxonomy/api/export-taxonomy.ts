import { backendRawRequest } from "@/shared/api/backend-client";

export interface TaxonomyExportResult {
  contentType: string;
  filename: string | null;
  body: string;
}

export async function exportTaxonomy(
  taxonomyId: string,
  format: "json" | "csv",
  includeOrphans: boolean,
): Promise<TaxonomyExportResult> {
  const response = await backendRawRequest(`/api/taxonomies/${taxonomyId}/export`, {
    query: {
      format,
      include_orphans: includeOrphans,
    },
  });

  const disposition = response.headers.get("content-disposition");
  const filenameMatch = disposition?.match(/filename=([^;]+)/i);

  return {
    contentType: response.headers.get("content-type") ?? "application/octet-stream",
    filename: filenameMatch?.[1]?.replaceAll('"', "") ?? null,
    body: await response.text(),
  };
}
