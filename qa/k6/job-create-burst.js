import { check, sleep } from "k6";

import { envFloat, envInt, get, jsonItems, post, safeJson } from "./common.js";

export const options = {
  scenarios: {
    burst: {
      executor: "per-vu-iterations",
      vus: envInt("VUS", 5),
      iterations: envInt("ITERATIONS", 6),
      maxDuration: __ENV.MAX_DURATION || "90s",
    },
  },
  thresholds: {
    http_req_failed: [`rate<${envFloat("MAX_FAILED_RATE", 0.2)}`],
    http_req_duration: [`p(95)<${envInt("P95_MS", 1800)}`],
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
      type: "FULL_PIPELINE",
      params: {
        method_term_extraction: "both",
        method_taxonomy: "hybrid",
        max_terms: 200,
        min_freq: 1,
        similarity_threshold: 0.55,
        chunk_size: 1000,
        max_depth: 6,
      },
    }),
  );

  check(jobRes, {
    "job create returns 201": (r) => r.status === 201,
    "job create returns id": (r) => Boolean(safeJson(r, "id")),
  });

  const job = safeJson(jobRes) || {};
  const taxonomyVersionId = job.taxonomyVersionId;

  if (job.id) {
    const statusRes = get(`/api/jobs/${job.id}`);
    check(statusRes, {
      "created job can be read back": (r) => r.status === 200,
    });

    const eventsRes = get(`/api/jobs/${job.id}/events`);
    check(eventsRes, {
      "created job events can be read": (r) => r.status === 200,
    });
  }

  if (taxonomyVersionId) {
    const versionRes = get(`/api/taxonomies/${taxonomyVersionId}`);
    check(versionRes, {
      "created taxonomy version can be read": (r) => r.status === 200,
    });

    const treeRes = get(`/api/taxonomies/${taxonomyVersionId}/tree`);
    check(treeRes, {
      "created taxonomy tree can be read": (r) => r.status === 200,
    });

    const edgesRes = get(`/api/taxonomies/${taxonomyVersionId}/edges?page=0&size=10`);
    check(edgesRes, {
      "created taxonomy edges can be read": (r) => r.status === 200,
    });

    const conceptsRes = get(`/api/taxonomies/${taxonomyVersionId}/concepts/search?q=${encodeURIComponent("tax")}&page=0&size=10`);
    check(conceptsRes, {
      "created taxonomy concepts can be searched": (r) => r.status === 200,
    });

    const concepts = jsonItems(conceptsRes);
    if (concepts.length > 0) {
      const conceptRes = get(`/api/taxonomies/${taxonomyVersionId}/concepts/${concepts[0].id}`);
      check(conceptRes, {
        "created taxonomy concept detail can be read": (r) => r.status === 200,
      });
    }

    const activeReleaseRes = post(
      `/api/collections/${collectionId}/releases`,
      JSON.stringify({
        taxonomyVersionId,
        releaseName: `qa-burst-active-${__VU}-${__ITER}`,
        channel: "active",
        trafficPercent: 100,
        notes: "created by k6 burst scenario",
      }),
    );
    check(activeReleaseRes, {
      "active release create returns 201": (r) => r.status === 201,
      "active release returns id": (r) => Boolean(safeJson(r, "id")),
    });

    const activeRelease = safeJson(activeReleaseRes) || {};
    if (activeRelease.id) {
      const canaryReleaseRes = post(
        `/api/collections/${collectionId}/releases`,
        JSON.stringify({
          taxonomyVersionId,
          releaseName: `qa-burst-canary-${__VU}-${__ITER}`,
          channel: "canary",
          trafficPercent: 10,
          notes: "created by k6 burst scenario",
        }),
      );
      check(canaryReleaseRes, {
        "canary release create returns 201": (r) => r.status === 201,
        "canary release returns id": (r) => Boolean(safeJson(r, "id")),
      });

      const canaryRelease = safeJson(canaryReleaseRes) || {};
      if (canaryRelease.id) {
        const promoteRes = post(
          `/api/collections/${collectionId}/releases/${canaryRelease.id}/promote`,
          JSON.stringify({
            channel: "active",
            trafficPercent: 100,
            notes: "promoted by k6 burst scenario",
          }),
        );
        check(promoteRes, {
          "release promote returns 200": (r) => r.status === 200,
        });

        if (__ITER % 2 === 0) {
          const rollbackRes = post(
            `/api/collections/${collectionId}/releases/${canaryRelease.id}/rollback`,
            JSON.stringify({
              rollbackToReleaseId: activeRelease.id,
              channel: "active",
              notes: "rollback by k6 burst scenario",
            }),
          );
          check(rollbackRes, {
            "release rollback returns 200": (r) => r.status === 200,
          });
        }
      }
    }
  }

  sleep(envFloat("SLEEP_SECONDS", 0.25));
}
