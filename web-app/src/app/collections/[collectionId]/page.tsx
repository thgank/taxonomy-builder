import { notFound } from "next/navigation";

import { getCollection } from "@/entities/collection/api/get-collection";
import { getCollectionDocuments } from "@/entities/document/api/get-collection-documents";
import { getCollectionReleases } from "@/entities/release/api/get-collection-releases";
import { getCollectionTaxonomies } from "@/entities/taxonomy/api/get-collection-taxonomies";
import { isApiError } from "@/shared/api/error";
import { CollectionOverview } from "@/widgets/collection-overview/collection-overview";

export default async function CollectionDetailPage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;
  let collectionData: Awaited<ReturnType<typeof getCollection>>;
  let documentsData: Awaited<ReturnType<typeof getCollectionDocuments>>;
  let taxonomyVersionsData: Awaited<ReturnType<typeof getCollectionTaxonomies>>;
  let releasesData: Awaited<ReturnType<typeof getCollectionReleases>>;

  try {
    [collectionData, documentsData, taxonomyVersionsData, releasesData] = await Promise.all([
      getCollection(collectionId),
      getCollectionDocuments(collectionId),
      getCollectionTaxonomies(collectionId),
      getCollectionReleases(collectionId),
    ]);
  } catch (error) {
    if (isApiError(error) && error.status === 404) {
      notFound();
    }

    throw error;
  }

  return (
    <CollectionOverview
      collection={collectionData}
      documents={documentsData}
      releases={releasesData}
      taxonomyVersions={taxonomyVersionsData}
    />
  );
}
