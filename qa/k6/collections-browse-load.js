import { check, sleep } from "k6";

import { envFloat, envInt, firstJsonItem, get, jsonItems, post, safeJson } from "./common.js";

export const options = {
  scenarios: {
    browse: {
      executor: "constant-vus",
      vus: envInt("VUS", 10),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.03)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 1200)}`],
  },
};

export function setup() {
  const collectionName = `qa-browse-${Date.now()}`;
  const response = post(
    "/api/collections",
    JSON.stringify({
      name: collectionName,
      description: "Created by k6 browse scenario",
    }),
  );

  check(response, {
    "setup collection created": (r) => r.status === 201,
  });

  return {
    collectionId: safeJson(response, "id"),
  };
}

export default function (data) {
  const listRes = get("/api/collections");
  check(listRes, {
    "list collections is 200": (r) => r.status === 200,
  });

  const collections = jsonItems(listRes);
  const activeCollection = collections.find((collection) => collection.id === data.collectionId) || firstJsonItem(listRes);

  if (data.collectionId) {
    const getRes = get(`/api/collections/${data.collectionId}`);
    check(getRes, {
      "get collection is 200": (r) => r.status === 200,
    });

    const documentsRes = get(`/api/collections/${data.collectionId}/documents`);
    check(documentsRes, {
      "list documents is 200": (r) => r.status === 200,
    });

    const taxonomiesRes = get(`/api/collections/${data.collectionId}/taxonomies`);
    check(taxonomiesRes, {
      "list taxonomies is 200": (r) => r.status === 200,
    });

    const releasesRes = get(`/api/collections/${data.collectionId}/releases`);
    check(releasesRes, {
      "list releases is 200": (r) => r.status === 200,
    });

    const taxonomyVersion = firstJsonItem(taxonomiesRes);
    const effectiveTaxonomyId = taxonomyVersion?.id || null;

    if (effectiveTaxonomyId) {
      const versionRes = get(`/api/taxonomies/${effectiveTaxonomyId}`);
      check(versionRes, {
        "get taxonomy version is 200": (r) => r.status === 200,
      });

      const treeRes = get(`/api/taxonomies/${effectiveTaxonomyId}/tree`);
      check(treeRes, {
        "get taxonomy tree is 200": (r) => r.status === 200,
      });

      const edgesRes = get(`/api/taxonomies/${effectiveTaxonomyId}/edges?page=0&size=5`);
      check(edgesRes, {
        "get taxonomy edges is 200": (r) => r.status === 200,
      });

      const labelsRes = get(`/api/taxonomies/${effectiveTaxonomyId}/labels?page=0&size=5`);
      check(labelsRes, {
        "get taxonomy labels is 200": (r) => r.status === 200,
      });

      const searchRes = get(`/api/taxonomies/${effectiveTaxonomyId}/concepts/search?q=${encodeURIComponent("tax")}&page=0&size=5`);
      check(searchRes, {
        "search concepts is 200": (r) => r.status === 200,
      });

      const concepts = jsonItems(searchRes);
      if (concepts.length > 0) {
        const conceptRes = get(`/api/taxonomies/${effectiveTaxonomyId}/concepts/${concepts[0].id}`);
        check(conceptRes, {
          "get concept detail is 200": (r) => r.status === 200,
        });
      }

      const exportJsonRes = get(`/api/taxonomies/${effectiveTaxonomyId}/export?format=json&include_orphans=true`);
      check(exportJsonRes, {
        "export taxonomy json is 200": (r) => r.status === 200,
      });

      if ((__ITER + __VU) % 4 === 0) {
        const exportCsvRes = get(`/api/taxonomies/${effectiveTaxonomyId}/export?format=csv&include_orphans=false`);
        check(exportCsvRes, {
          "export taxonomy csv is 200": (r) => r.status === 200,
        });
      }
    }
  }

  if (activeCollection?.id && __ITER % 3 === 0) {
    const secondaryDocsRes = get(`/api/collections/${activeCollection.id}/documents`);
    check(secondaryDocsRes, {
      "secondary collection documents is 200": (r) => r.status === 200,
    });
  }

  sleep(envFloat("SLEEP_SECONDS", 0.5));
}
