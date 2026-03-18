import { notFound } from "next/navigation";

import { getConceptDetail } from "@/entities/taxonomy/api/get-concept-detail";
import { getTaxonomyEdges } from "@/entities/taxonomy/api/get-taxonomy-edges";
import { getTaxonomyLabels } from "@/entities/taxonomy/api/get-taxonomy-labels";
import { getTaxonomyTree } from "@/entities/taxonomy/api/get-taxonomy-tree";
import { getTaxonomyVersion } from "@/entities/taxonomy/api/get-taxonomy-version";
import { searchTaxonomyConcepts } from "@/entities/taxonomy/api/search-taxonomy-concepts";
import { isApiError } from "@/shared/api/error";
import { getPaginationFromSearchParams } from "@/shared/lib/pagination";
import { TaxonomyExplorer } from "@/widgets/taxonomy-explorer/taxonomy-explorer";

export default async function TaxonomyDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ taxonomyId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { taxonomyId } = await params;
  const resolvedSearchParams = await searchParams;
  const edgePagination = getPaginationFromSearchParams(
    {
      page: resolvedSearchParams.edgePage,
      size: resolvedSearchParams.edgeSize,
    },
    { page: 0, size: 10 },
  );
  const labelPagination = getPaginationFromSearchParams(
    {
      page: resolvedSearchParams.labelPage,
      size: resolvedSearchParams.labelSize,
    },
    { page: 0, size: 10 },
  );
  const conceptPagination = getPaginationFromSearchParams(
    {
      page: resolvedSearchParams.conceptPage,
      size: resolvedSearchParams.conceptSize,
    },
    { page: 0, size: 8 },
  );
  const searchQuery =
    typeof resolvedSearchParams.q === "string" ? resolvedSearchParams.q.trim() : "";
  const conceptId =
    typeof resolvedSearchParams.conceptId === "string" ? resolvedSearchParams.conceptId : null;

  let versionData: Awaited<ReturnType<typeof getTaxonomyVersion>>;
  let treeData: Awaited<ReturnType<typeof getTaxonomyTree>>;
  let edgesData: Awaited<ReturnType<typeof getTaxonomyEdges>>;
  let labelsData: Awaited<ReturnType<typeof getTaxonomyLabels>>;
  let conceptsData: Awaited<ReturnType<typeof searchTaxonomyConcepts>> | null = null;
  let selectedConceptData: Awaited<ReturnType<typeof getConceptDetail>> | null = null;

  try {
    [versionData, treeData, edgesData, labelsData] = await Promise.all([
      getTaxonomyVersion(taxonomyId),
      getTaxonomyTree(taxonomyId),
      getTaxonomyEdges(taxonomyId, edgePagination),
      getTaxonomyLabels(taxonomyId, labelPagination),
    ]);

    if (searchQuery) {
      conceptsData = await searchTaxonomyConcepts(taxonomyId, searchQuery, conceptPagination);
    }

    if (conceptId) {
      selectedConceptData = await getConceptDetail(taxonomyId, conceptId);
    }
  } catch (error) {
    if (isApiError(error) && error.status === 404) {
      notFound();
    }

    throw error;
  }

  return (
    <TaxonomyExplorer
      concepts={conceptsData}
      edges={edgesData}
      labels={labelsData}
      searchParams={resolvedSearchParams}
      searchQuery={searchQuery}
      selectedConcept={selectedConceptData}
      taxonomyId={taxonomyId}
      tree={treeData}
      version={versionData}
    />
  );
}
