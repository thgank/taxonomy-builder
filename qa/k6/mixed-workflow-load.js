import { check, sleep } from "k6";

import { envFloat, envInt, firstJsonItem, get, jsonItems, post, safeJson } from "./common.js";

export const options = {
  scenarios: {
    mixed: {
      executor: "constant-vus",
      vus: envInt("VUS", 14),
      duration: __ENV.DURATION || "90s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.08)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 1800)}`],
  },
};

const taxonomyId = __ENV.TAXONOMY_ID || "";

function maybeCreateCollection() {
  const shouldCreate = (__ITER + __VU) % 3 === 0;
  if (!shouldCreate) {
    return null;
  }

  const res = post(
    "/api/collections",
    JSON.stringify({
      name: `qa-mixed-${__VU}-${__ITER}-${Date.now()}`,
      description: "Created by mixed workflow load scenario",
    }),
  );

  check(res, {
    "mixed create collection returns 201": (r) => r.status === 201,
  });

  return safeJson(res, "id");
}

function maybeCreateImportJob(collectionId) {
  if (!collectionId) {
    return;
  }
  const shouldCreateJob = (__ITER + __VU) % 4 === 0;
  if (!shouldCreateJob) {
    return;
  }

  const res = post(
    `/api/collections/${collectionId}/jobs`,
    JSON.stringify({
      type: (__ITER + __VU) % 2 === 0 ? "FULL_PIPELINE" : "TAXONOMY",
      params: {
        method_term_extraction: "both",
        method_taxonomy: "hybrid",
        max_terms: 150,
        min_freq: 1,
        similarity_threshold: 0.5,
        chunk_size: 1000,
        max_depth: 6,
      },
    }),
  );

  check(res, {
    "mixed create job returns 201 or 409": (r) => r.status === 201 || r.status === 409,
  });
}

function maybeReadTaxonomy(collectionId, taxonomyId) {
  if (!collectionId) {
    return;
  }

  const versionsRes = get(`/api/collections/${collectionId}/taxonomies`);
  check(versionsRes, {
    "mixed list taxonomies is 200": (r) => r.status === 200,
  });

  const releasesRes = get(`/api/collections/${collectionId}/releases`);
  check(releasesRes, {
    "mixed list releases is 200": (r) => r.status === 200,
  });

  const version = taxonomyId ? { id: taxonomyId } : firstJsonItem(versionsRes);
  const effectiveTaxonomyId = version?.id || null;
  if (!effectiveTaxonomyId) {
    return;
  }

  const versionRes = get(`/api/taxonomies/${effectiveTaxonomyId}`);
  check(versionRes, {
    "mixed get taxonomy version is 200": (r) => r.status === 200,
  });

  const treeRes = get(`/api/taxonomies/${effectiveTaxonomyId}/tree`);
  check(treeRes, {
    "mixed get tree is 200": (r) => r.status === 200,
  });

  const edgesRes = get(`/api/taxonomies/${effectiveTaxonomyId}/edges?page=0&size=10`);
  check(edgesRes, {
    "mixed get edges is 200": (r) => r.status === 200,
  });

  const labelsRes = get(`/api/taxonomies/${effectiveTaxonomyId}/labels?page=0&size=10`);
  check(labelsRes, {
    "mixed get labels is 200": (r) => r.status === 200,
  });

  const conceptsRes = get(`/api/taxonomies/${effectiveTaxonomyId}/concepts/search?q=${encodeURIComponent("tax")}&page=0&size=10`);
  check(conceptsRes, {
    "mixed search concepts is 200": (r) => r.status === 200,
  });

  const concepts = jsonItems(conceptsRes);
  if (concepts.length >= 2) {
    const labelRes = post(
      `/api/taxonomies/${effectiveTaxonomyId}/labels`,
      JSON.stringify({
        parentConceptId: concepts[0].id,
        childConceptId: concepts[1].id,
        parentLabel: concepts[0].canonical,
        childLabel: concepts[1].canonical,
        label: (__ITER + __VU) % 2 === 0 ? "accepted" : "rejected",
        labelSource: "k6-mixed",
        reviewerId: "k6",
        reason: "mixed workflow load",
        meta: { scenario: "mixed-workflow-load" },
      }),
    );
    check(labelRes, {
      "mixed create label is 201": (r) => r.status === 201,
    });
  }

  if (concepts.length > 0) {
    const conceptRes = get(`/api/taxonomies/${effectiveTaxonomyId}/concepts/${concepts[0].id}`);
    check(conceptRes, {
      "mixed concept detail is 200": (r) => r.status === 200,
    });
  }

  const exportJsonRes = get(`/api/taxonomies/${effectiveTaxonomyId}/export?format=json&include_orphans=true`);
  check(exportJsonRes, {
    "mixed export json is 200": (r) => r.status === 200,
  });

  if (__ITER % 3 === 0) {
    const exportCsvRes = get(`/api/taxonomies/${effectiveTaxonomyId}/export?format=csv&include_orphans=false`);
    check(exportCsvRes, {
      "mixed export csv is 200": (r) => r.status === 200,
    });
  }
}

export default function () {
  const listCollectionsRes = get("/api/collections");
  check(listCollectionsRes, {
    "mixed list collections is 200": (r) => r.status === 200,
  });

  const listCollections = jsonItems(listCollectionsRes);

  const collectionId = maybeCreateCollection();
  const activeCollectionId = collectionId || (listCollections.length > 0 ? listCollections[0].id : null);

  if (activeCollectionId) {
    const getCollectionRes = get(`/api/collections/${activeCollectionId}`);
    check(getCollectionRes, {
      "mixed get collection is 200": (r) => r.status === 200,
    });

    const listDocumentsRes = get(`/api/collections/${activeCollectionId}/documents`);
    check(listDocumentsRes, {
      "mixed list documents is 200": (r) => r.status === 200,
    });

    const listTaxonomiesRes = get(`/api/collections/${activeCollectionId}/taxonomies`);
    check(listTaxonomiesRes, {
      "mixed list taxonomies is 200": (r) => r.status === 200,
    });

    const listReleasesRes = get(`/api/collections/${activeCollectionId}/releases`);
    check(listReleasesRes, {
      "mixed list releases is 200": (r) => r.status === 200,
    });

    const versions = jsonItems(listTaxonomiesRes);
    const taxonomyVersionId = taxonomyId || (versions.length > 0 ? versions[0].id : null);

    if (taxonomyVersionId) {
      const versionRes = get(`/api/taxonomies/${taxonomyVersionId}`);
      check(versionRes, {
        "mixed read taxonomy version is 200": (r) => r.status === 200,
      });

      const treeRes = get(`/api/taxonomies/${taxonomyVersionId}/tree`);
      check(treeRes, {
        "mixed read tree is 200": (r) => r.status === 200,
      });

      const edgesRes = get(`/api/taxonomies/${taxonomyVersionId}/edges?page=0&size=10`);
      check(edgesRes, {
        "mixed read edges is 200": (r) => r.status === 200,
      });

      const conceptsRes = get(`/api/taxonomies/${taxonomyVersionId}/concepts/search?q=${encodeURIComponent("tax")}&page=0&size=10`);
      check(conceptsRes, {
        "mixed concept search is 200": (r) => r.status === 200,
      });

      const concepts = jsonItems(conceptsRes);
      if (concepts.length > 0) {
        const conceptRes = get(`/api/taxonomies/${taxonomyVersionId}/concepts/${concepts[0].id}`);
        check(conceptRes, {
          "mixed concept detail is 200": (r) => r.status === 200,
        });
      }

      if (versions.length > 0 && concepts.length >= 2 && __ITER % 3 === 0) {
        const releaseRes = post(
          `/api/collections/${activeCollectionId}/releases`,
          JSON.stringify({
            taxonomyVersionId,
            releaseName: `qa-mixed-${__VU}-${__ITER}-${Date.now()}`,
            channel: __ITER % 2 === 0 ? "active" : "canary",
            trafficPercent: __ITER % 2 === 0 ? 100 : 10,
            notes: "Created by mixed workflow load scenario",
          }),
        );
        check(releaseRes, {
          "mixed create release is 201": (r) => r.status === 201,
        });
      }
    }
  }

  maybeCreateImportJob(activeCollectionId);
  maybeReadTaxonomy(activeCollectionId, taxonomyId);

  sleep(envFloat("SLEEP_SECONDS", 0.25));
}
