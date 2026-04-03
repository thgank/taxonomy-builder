import { check, sleep } from "k6";
import { envInt, envFloat, get, post, safeJson } from "./common.js";

export const options = {
  vus: envInt("VUS", 1),
  iterations: envInt("ITERATIONS", 1),
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.05)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 1500)}`],
  },
};

const runJob = (__ENV.RUN_JOB || "false").toLowerCase() === "true";

export default function () {
  const collectionName = `qa-smoke-${Date.now()}`;
  const createCollectionPayload = JSON.stringify({
    name: collectionName,
    description: "Created by k6 smoke test",
  });

  const createCollectionRes = post("/api/collections", createCollectionPayload);

  check(createCollectionRes, {
    "create collection status is 201": (r) => r.status === 201,
    "create collection returns id": (r) => Boolean(safeJson(r, "id")),
  });

  const collectionId = safeJson(createCollectionRes, "id");
  if (!collectionId) {
    return;
  }

  const listCollectionsRes = get("/api/collections");

  check(listCollectionsRes, {
    "list collections status is 200": (r) => r.status === 200,
  });

  const getCollectionRes = get(`/api/collections/${collectionId}`);

  check(getCollectionRes, {
    "get collection status is 200": (r) => r.status === 200,
    "get collection name matches": (r) => safeJson(r, "name") === collectionName,
  });

  if (runJob) {
    const createJobPayload = JSON.stringify({
      type: "FULL_PIPELINE",
      params: {
        method_term_extraction: "both",
        method_taxonomy: "hybrid",
        max_terms: 100,
        min_freq: 1,
        similarity_threshold: 0.55,
        chunk_size: 1000,
      },
    });

    const createJobRes = post(`/api/collections/${collectionId}/jobs`, createJobPayload);

    check(createJobRes, {
      "create job returns accepted object": (r) => r.status === 201,
      "create job returns job id": (r) => Boolean(safeJson(r, "id")),
    });
  }

  sleep(envFloat("SLEEP_SECONDS", 1));
}
