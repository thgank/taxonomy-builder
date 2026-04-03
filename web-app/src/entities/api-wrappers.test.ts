import assert from "node:assert/strict";
import test from "node:test";

import { importFresh, mockModule, restoreModules } from "../../test/module-test-utils";

test("entity API wrappers send correct requests and normalize responses", async () => {
  const backendCalls: Array<{ path: string; options: unknown }> = [];
  mockModule("@/shared/api/backend-client", {
    backendRequest: async (path: string, options: unknown) => {
      backendCalls.push({ path, options });

      if (path === "/api/collections") {
        return { id: "col-1", name: "Energy" };
      }
      if (path === "/api/collections/col-1/jobs") {
        return { id: "job-1" };
      }
      if (path === "/api/collections/col-1/documents:upload") {
        return [
          {
            id: "doc-1",
            filename: "report.pdf",
            status: "PARSED",
          },
        ];
      }
      if (path === "/api/taxonomies/tax-1/edges") {
        return {
          id: "edge-1",
          parentLabel: "energy",
          childLabel: "battery storage",
          evidence: [{ method: "manual" }],
        };
      }
      if (path === "/api/jobs/job-1:cancel") {
        return {
          id: "job-1",
          collectionId: "col-1",
        };
      }
      if (path === "/api/collections/col-1/releases") {
        return {
          id: "rel-1",
          collectionId: "col-1",
          releaseName: "spring",
          qualitySnapshot: { lcr: 0.91 },
        };
      }
      if (path === "/api/collections/col-1/releases/rel-1/promote") {
        return {
          id: "rel-1",
          collectionId: "col-1",
          channel: "canary",
        };
      }
      if (path === "/api/collections/col-1/releases/rel-1/rollback") {
        return {
          id: "rel-rollback",
          collectionId: "col-1",
          rollbackOf: "rel-1",
        };
      }

      throw new Error(`Unexpected path ${path}`);
    },
  });

  const { createCollection } = importFresh<typeof import("./collection/api/create-collection")>(
    "@/entities/collection/api/create-collection",
  );
  const { createJob } = importFresh<typeof import("./job/api/create-job")>(
    "@/entities/job/api/create-job",
  );
  const { uploadCollectionDocuments } = importFresh<typeof import("./document/api/upload-documents")>(
    "@/entities/document/api/upload-documents",
  );
  const { createTaxonomyEdge } = importFresh<typeof import("./taxonomy/api/create-taxonomy-edge")>(
    "@/entities/taxonomy/api/create-taxonomy-edge",
  );
  const { cancelJob } = importFresh<typeof import("./job/api/cancel-job")>(
    "@/entities/job/api/cancel-job",
  );
  const { createRelease } = importFresh<typeof import("./release/api/create-release")>(
    "@/entities/release/api/create-release",
  );
  const { promoteRelease } = importFresh<typeof import("./release/api/promote-release")>(
    "@/entities/release/api/promote-release",
  );
  const { rollbackRelease } = importFresh<typeof import("./release/api/rollback-release")>(
    "@/entities/release/api/rollback-release",
  );

  const collection = await createCollection({ name: "Energy" });
  const job = await createJob("col-1", { type: "IMPORT", params: {} });
  const documents = await uploadCollectionDocuments("col-1", [new File(["x"], "report.pdf")]);
  const edge = await createTaxonomyEdge("tax-1", {
    parentConceptId: "parent-1",
    childConceptId: "child-1",
  });
  const cancelledJob = await cancelJob("job-1");
  const release = await createRelease("col-1", { releaseName: "spring" });
  const promoted = await promoteRelease("col-1", "rel-1", { channel: "canary" });
  const rolledBack = await rollbackRelease("col-1", "rel-1", { rollbackToReleaseId: "rel-0" });

  assert.equal(collection.id, "col-1");
  assert.equal(job.id, "job-1");
  assert.equal(documents[0]?.collectionId, "col-1");
  assert.equal(documents[0]?.mimeType, "application/octet-stream");
  assert.equal(edge.parentConceptId, "parent-1");
  assert.deepEqual(edge.evidence, [{ method: "manual" }]);
  assert.equal(cancelledJob.status, "CANCELLED");
  assert.deepEqual(release.qualitySnapshot, { lcr: 0.91 });
  assert.equal(promoted.channel, "canary");
  assert.equal(rolledBack.id, "rel-rollback");

  assert.equal(backendCalls[0]?.path, "/api/collections");
  assert.equal(
    backendCalls.some((call) => call.path === "/api/collections/col-1/documents:upload"),
    true,
  );

  restoreModules([
    "@/shared/api/backend-client",
    "@/entities/collection/api/create-collection",
    "@/entities/job/api/create-job",
    "@/entities/document/api/upload-documents",
    "@/entities/taxonomy/api/create-taxonomy-edge",
    "@/entities/job/api/cancel-job",
    "@/entities/release/api/create-release",
    "@/entities/release/api/promote-release",
    "@/entities/release/api/rollback-release",
  ]);
});
