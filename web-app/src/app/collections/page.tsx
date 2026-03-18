import { getCollections } from "@/entities/collection/api/get-collections";
import { CollectionsOverview } from "@/widgets/collections-overview/collections-overview";

export default async function CollectionsPage() {
  const collections = await getCollections();

  return <CollectionsOverview collections={collections} />;
}
