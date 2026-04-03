import { check, sleep } from "k6";

import { envFloat, envInt, get, post, safeJson } from "./common.js";

export const options = {
  scenarios: {
    mixed: {
      executor: "constant-vus",
      vus: envInt("VUS", 8),
      duration: __ENV.DURATION || "45s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.1)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 2000)}`],
  },
};

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
  const shouldCreateJob = (__ITER + __VU) % 5 === 0;
  if (!shouldCreateJob) {
    return;
  }

  const res = post(
    `/api/collections/${collectionId}/jobs`,
    JSON.stringify({
      type: "IMPORT",
      params: {
        chunk_size: 1000,
      },
    }),
  );

  check(res, {
    "mixed create job returns 201 or 409": (r) => r.status === 201 || r.status === 409,
  });
}

export default function () {
  const listCollectionsRes = get("/api/collections");
  check(listCollectionsRes, {
    "mixed list collections is 200": (r) => r.status === 200,
  });

  const collectionId = maybeCreateCollection();

  if (collectionId) {
    const getCollectionRes = get(`/api/collections/${collectionId}`);
    check(getCollectionRes, {
      "mixed get collection is 200": (r) => r.status === 200,
    });
  }

  maybeCreateImportJob(collectionId);

  sleep(envFloat("SLEEP_SECONDS", 0.5));
}
