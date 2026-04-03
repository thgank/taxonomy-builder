import { check, sleep } from "k6";

import { envFloat, envInt, post, safeJson } from "./common.js";

export const options = {
  scenarios: {
    burst: {
      executor: "per-vu-iterations",
      vus: envInt("VUS", 3),
      iterations: envInt("ITERATIONS", 2),
      maxDuration: __ENV.MAX_DURATION || "30s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.2)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 2000)}`],
  },
};

export default function () {
  const collectionRes = post(
    "/api/collections",
    JSON.stringify({
      name: `qa-job-burst-${__VU}-${__ITER}-${Date.now()}`,
      description: "Created by k6 job burst scenario",
    }),
  );

  check(collectionRes, {
    "collection create is 201": (r) => r.status === 201,
  });

  const collectionId = safeJson(collectionRes, "id");
  if (!collectionId) {
    return;
  }

  const jobRes = post(
    `/api/collections/${collectionId}/jobs`,
    JSON.stringify({
      type: "IMPORT",
      params: {
        chunk_size: 1000,
      },
    }),
  );

  check(jobRes, {
    "job create returns 201": (r) => r.status === 201,
    "job create returns id": (r) => Boolean(safeJson(r, "id")),
  });

  sleep(envFloat("SLEEP_SECONDS", 1));
}
