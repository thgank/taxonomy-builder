import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    polling: {
      executor: "constant-vus",
      vus: 5,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1200"],
  },
};

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";
const apiKey = __ENV.API_KEY || "dev-api-key-change-me";
const jobId = __ENV.JOB_ID;
const taxonomyId = __ENV.TAXONOMY_ID;

if (!jobId) {
  throw new Error("JOB_ID is required");
}

const authHeaders = {
  headers: {
    "X-API-Key": apiKey,
  },
};

export default function () {
  const jobRes = http.get(`${baseUrl}/api/jobs/${jobId}`, authHeaders);
  check(jobRes, {
    "job status endpoint returns 200": (r) => r.status === 200,
  });

  const eventsRes = http.get(`${baseUrl}/api/jobs/${jobId}/events`, authHeaders);
  check(eventsRes, {
    "job events endpoint returns 200": (r) => r.status === 200,
  });

  if (taxonomyId) {
    const treeRes = http.get(
      `${baseUrl}/api/taxonomies/${taxonomyId}/tree`,
      authHeaders,
    );
    check(treeRes, {
      "taxonomy tree endpoint returns 200": (r) => r.status === 200,
    });
  }

  sleep(1);
}
