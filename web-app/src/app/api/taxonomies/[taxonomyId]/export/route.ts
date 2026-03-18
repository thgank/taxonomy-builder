import { exportTaxonomy } from "@/entities/taxonomy/api/export-taxonomy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ taxonomyId: string }> },
) {
  const { taxonomyId } = await params;
  const url = new URL(request.url);
  const format = url.searchParams.get("format") === "csv" ? "csv" : "json";
  const includeOrphans = url.searchParams.get("include_orphans") === "true";

  const result = await exportTaxonomy(taxonomyId, format, includeOrphans);

  return new Response(result.body, {
    headers: {
      "content-type": result.contentType,
      ...(result.filename ? { "content-disposition": `attachment; filename="${result.filename}"` } : {}),
    },
  });
}
