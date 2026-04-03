import { check, sleep } from "k6";
import { envFloat, envInt, get } from "./common.js";

export const options = {
  scenarios: {
    polling: {
      executor: "constant-vus",
      vus: envInt("VUS", 5),
      duration: __ENV.DURATION || "30s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.05)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 1200)}`],
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

  const eventsRes = get(`/api/jobs/${jobId}/events`);
  check(eventsRes, {
    "job events endpoint returns 200": (r) => r.status === 200,
  });

  if (taxonomyId) {
    const treeRes = get(`/api/taxonomies/${taxonomyId}/tree`);
    check(treeRes, {
      "taxonomy tree endpoint returns 200": (r) => r.status === 200,
    });
  }

  sleep(envFloat("SLEEP_SECONDS", 1));
}
