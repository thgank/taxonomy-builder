import { check, sleep } from "k6";

import { envFloat, envInt, get, post, safeJson } from "./common.js";

export const options = {
  scenarios: {
    browse: {
      executor: "constant-vus",
      vus: envInt("VUS", 5),
      duration: __ENV.DURATION || "20s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.05)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 1500)}`],
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

  if (data.collectionId) {
    const getRes = get(`/api/collections/${data.collectionId}`);
    check(getRes, {
      "get collection is 200": (r) => r.status === 200,
    });
  }

  sleep(envFloat("SLEEP_SECONDS", 1));
}
