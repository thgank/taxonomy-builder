import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1500"],
  },
};

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";
const apiKey = __ENV.API_KEY || "dev-api-key-change-me";
const runJob = (__ENV.RUN_JOB || "false").toLowerCase() === "true";

function headers(contentType = "application/json") {
  return {
    headers: {
      "Content-Type": contentType,
      "X-API-Key": apiKey,
    },
  };
}

export default function () {
  const collectionName = `qa-smoke-${Date.now()}`;
  const createCollectionPayload = JSON.stringify({
    name: collectionName,
    description: "Created by k6 smoke test",
  });

  const createCollectionRes = http.post(
    `${baseUrl}/api/collections`,
    createCollectionPayload,
    headers(),
  );

  check(createCollectionRes, {
    "create collection status is 201": (r) => r.status === 201,
    "create collection returns id": (r) => {
      try {
        return Boolean(r.json("id"));
      } catch (_) {
        return false;
      }
    },
  });

  const collectionId = createCollectionRes.json("id");
  if (!collectionId) {
    return;
  }

  const listCollectionsRes = http.get(
    `${baseUrl}/api/collections`,
    { headers: { "X-API-Key": apiKey } },
  );

  check(listCollectionsRes, {
    "list collections status is 200": (r) => r.status === 200,
  });

  const getCollectionRes = http.get(
    `${baseUrl}/api/collections/${collectionId}`,
    { headers: { "X-API-Key": apiKey } },
  );

  check(getCollectionRes, {
    "get collection status is 200": (r) => r.status === 200,
    "get collection name matches": (r) => r.json("name") === collectionName,
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

    const createJobRes = http.post(
      `${baseUrl}/api/collections/${collectionId}/jobs`,
      createJobPayload,
      headers(),
    );

    check(createJobRes, {
      "create job returns accepted object": (r) => r.status === 201,
      "create job returns job id": (r) => {
        try {
          return Boolean(r.json("id"));
        } catch (_) {
          return false;
        }
      },
    });
  }

  sleep(1);
}
