import { check, sleep } from "k6";
import { envFloat, envInt, firstJsonItem, get, jsonItems, safeJson } from "./common.js";

export const options = {
  scenarios: {
    polling: {
      executor: "constant-vus",
      vus: envInt("VUS", 12),
      duration: __ENV.DURATION || "90s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.03)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 1000)}`],
  },
};

const jobId = __ENV.JOB_ID;
const taxonomyId = __ENV.TAXONOMY_ID;

if (!jobId) {
  throw new Error("JOB_ID is required");
}

export default function () {
  const jobRes = get(`/api/jobs/${jobId}`);
  check(jobRes, {
    "job status endpoint returns 200": (r) => r.status === 200,
  });

  const job = safeJson(jobRes) || {};
  const collectionId = job.collectionId;
  const effectiveTaxonomyId = taxonomyId || job.taxonomyVersionId || null;

  const collectionsRes = get("/api/collections");
  check(collectionsRes, {
    "collections endpoint returns 200": (r) => r.status === 200,
  });

  if (collectionId) {
    const collectionRes = get(`/api/collections/${collectionId}`);
    check(collectionRes, {
      "job collection endpoint returns 200": (r) => r.status === 200,
    });

    const documentsRes = get(`/api/collections/${collectionId}/documents`);
    check(documentsRes, {
      "job collection documents return 200": (r) => r.status === 200,
    });

    const versionListRes = get(`/api/collections/${collectionId}/taxonomies`);
    check(versionListRes, {
      "job collection taxonomies return 200": (r) => r.status === 200,
    });

    const releaseListRes = get(`/api/collections/${collectionId}/releases`);
    check(releaseListRes, {
      "job collection releases return 200": (r) => r.status === 200,
    });

    const versionFromList = firstJsonItem(versionListRes);
    const taxonomyVersionId = effectiveTaxonomyId || versionFromList?.id || null;

    if (taxonomyVersionId) {
      const versionRes = get(`/api/taxonomies/${taxonomyVersionId}`);
      check(versionRes, {
        "taxonomy version returns 200": (r) => r.status === 200,
      });

      const treeRes = get(`/api/taxonomies/${taxonomyVersionId}/tree`);
      check(treeRes, {
        "taxonomy tree returns 200": (r) => r.status === 200,
      });

      const edgesRes = get(`/api/taxonomies/${taxonomyVersionId}/edges?page=0&size=10`);
      check(edgesRes, {
        "taxonomy edges return 200": (r) => r.status === 200,
      });

      const labelsRes = get(`/api/taxonomies/${taxonomyVersionId}/labels?page=0&size=10`);
      check(labelsRes, {
        "taxonomy labels return 200": (r) => r.status === 200,
      });

      const searchRes = get(`/api/taxonomies/${taxonomyVersionId}/concepts/search?q=${encodeURIComponent("tax")}&page=0&size=5`);
      check(searchRes, {
        "concept search returns 200": (r) => r.status === 200,
      });

      const concepts = jsonItems(searchRes);
      if (concepts.length > 0) {
        const conceptRes = get(`/api/taxonomies/${taxonomyVersionId}/concepts/${concepts[0].id}`);
        check(conceptRes, {
          "concept detail returns 200": (r) => r.status === 200,
        });
      }

      const exportJsonRes = get(`/api/taxonomies/${taxonomyVersionId}/export?format=json&include_orphans=true`);
      check(exportJsonRes, {
        "taxonomy export json returns 200": (r) => r.status === 200,
      });

      if (__ITER % 4 === 0) {
        const exportCsvRes = get(`/api/taxonomies/${taxonomyVersionId}/export?format=csv&include_orphans=false`);
        check(exportCsvRes, {
          "taxonomy export csv returns 200": (r) => r.status === 200,
        });
      }
    }
  }

  const eventsRes = get(`/api/jobs/${jobId}/events`);
  check(eventsRes, {
    "job events endpoint returns 200": (r) => r.status === 200,
  });

  sleep(envFloat("SLEEP_SECONDS", 0.25));
}
