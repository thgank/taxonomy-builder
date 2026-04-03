import assert from "node:assert/strict";
import test from "node:test";

import { importFresh, mockModule, restoreModules } from "../../../../test/module-test-utils";

const nextCache = require("next/cache") as {
  __getCalls(): string[];
  __reset(): void;
};

test("taxonomy control actions call APIs and revalidate taxonomy page", async () => {
  nextCache.__reset();
  mockModule("@/entities/taxonomy/api/create-taxonomy-edge", {
    createTaxonomyEdge: async (taxonomyId: string, payload: unknown) => {
      assert.equal(taxonomyId, "tax-1");
      assert.deepEqual(payload, {
        parentConceptId: "parent-1",
        childConceptId: "child-1",
        relation: "is_a",
        score: 0.75,
      });
    },
  });
  mockModule("@/entities/taxonomy/api/create-taxonomy-label", {
    createTaxonomyLabel: async (taxonomyId: string, payload: unknown) => {
      assert.equal(taxonomyId, "tax-1");
      assert.deepEqual(payload, {
        candidateId: "cand-1",
        parentConceptId: undefined,
        childConceptId: undefined,
        parentLabel: "energy",
        childLabel: "battery storage",
        label: "accepted",
        labelSource: "manual",
        reviewerId: "qa",
        reason: "verified",
        meta: undefined,
      });
    },
  });
  mockModule("@/entities/taxonomy/api/update-taxonomy-edge", {
    updateTaxonomyEdge: async (taxonomyId: string, edgeId: string, payload: unknown) => {
      assert.equal(taxonomyId, "tax-1");
      assert.equal(edgeId, "edge-1");
      assert.deepEqual(payload, {
        score: 0.8,
        approved: true,
      });
    },
  });
  mockModule("@/entities/taxonomy/api/delete-taxonomy-edge", {
    deleteTaxonomyEdge: async (taxonomyId: string, edgeId: string) => {
      assert.equal(taxonomyId, "tax-1");
      assert.equal(edgeId, "edge-1");
    },
  });

  const importedActions = importFresh<typeof import("./taxonomy-controls-actions")>(
    "@/features/taxonomy-controls/actions/taxonomy-controls-actions",
  );

  const createEdgeData = new FormData();
  createEdgeData.set("parentConceptId", "parent-1");
  createEdgeData.set("childConceptId", "child-1");
  createEdgeData.set("relation", "is_a");
  createEdgeData.set("score", "0.75");
  const edgeResult = await importedActions.createTaxonomyEdgeAction("tax-1", { status: "idle" }, createEdgeData);

  const labelData = new FormData();
  labelData.set("candidateId", "cand-1");
  labelData.set("parentLabel", "energy");
  labelData.set("childLabel", "battery storage");
  labelData.set("label", "accepted");
  labelData.set("labelSource", "manual");
  labelData.set("reviewerId", "qa");
  labelData.set("reason", "verified");
  const labelResult = await importedActions.createTaxonomyLabelAction("tax-1", { status: "idle" }, labelData);

  const updateData = new FormData();
  updateData.set("score", "0.8");
  updateData.set("approved", "on");
  await importedActions.updateTaxonomyEdgeAction("tax-1", "edge-1", updateData);
  await importedActions.deleteTaxonomyEdgeAction("tax-1", "edge-1");

  assert.deepEqual(edgeResult, { status: "success", message: "Edge created." });
  assert.deepEqual(labelResult, { status: "success", message: "Label created." });
  assert.deepEqual(nextCache.__getCalls(), [
    "/taxonomies/tax-1",
    "/taxonomies/tax-1",
    "/taxonomies/tax-1",
    "/taxonomies/tax-1",
  ]);

  restoreModules([
    "@/features/taxonomy-controls/actions/taxonomy-controls-actions",
    "@/entities/taxonomy/api/create-taxonomy-edge",
    "@/entities/taxonomy/api/create-taxonomy-label",
    "@/entities/taxonomy/api/update-taxonomy-edge",
    "@/entities/taxonomy/api/delete-taxonomy-edge",
  ]);
});

test("taxonomy control actions convert thrown errors into action state", async () => {
  mockModule("@/entities/taxonomy/api/create-taxonomy-edge", {
    createTaxonomyEdge: async () => {
      throw new Error("edge failed");
    },
  });
  mockModule("@/entities/taxonomy/api/create-taxonomy-label", {
    createTaxonomyLabel: async () => {
      throw new Error("label failed");
    },
  });
  mockModule("@/entities/taxonomy/api/update-taxonomy-edge", {
    updateTaxonomyEdge: async () => undefined,
  });
  mockModule("@/entities/taxonomy/api/delete-taxonomy-edge", {
    deleteTaxonomyEdge: async () => undefined,
  });

  const importedActions = importFresh<typeof import("./taxonomy-controls-actions")>(
    "@/features/taxonomy-controls/actions/taxonomy-controls-actions",
  );

  const edgeResult = await importedActions.createTaxonomyEdgeAction("tax-1", { status: "idle" }, new FormData());
  const labelResult = await importedActions.createTaxonomyLabelAction("tax-1", { status: "idle" }, new FormData());

  assert.deepEqual(edgeResult, { status: "error", message: "edge failed" });
  assert.deepEqual(labelResult, { status: "error", message: "label failed" });

  restoreModules([
    "@/features/taxonomy-controls/actions/taxonomy-controls-actions",
    "@/entities/taxonomy/api/create-taxonomy-edge",
    "@/entities/taxonomy/api/create-taxonomy-label",
    "@/entities/taxonomy/api/update-taxonomy-edge",
    "@/entities/taxonomy/api/delete-taxonomy-edge",
  ]);
});
