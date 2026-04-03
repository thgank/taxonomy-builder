import assert from "node:assert/strict";
import test from "node:test";

import { importFresh, mockModule, restoreModules } from "../../../../test/module-test-utils";

const nextCache = require("next/cache") as {
  __getCalls(): string[];
  __reset(): void;
};

test("release actions create, promote, and rollback releases", async () => {
  nextCache.__reset();
  mockModule("@/entities/release/api/create-release", {
    createRelease: async (collectionId: string, payload: unknown) => {
      assert.equal(collectionId, "col-1");
      assert.deepEqual(payload, {
        taxonomyVersionId: "tax-1",
        releaseName: "Spring",
        channel: "canary",
        trafficPercent: 15,
        notes: "qa",
      });
    },
  });
  mockModule("@/entities/release/api/promote-release", {
    promoteRelease: async (collectionId: string, releaseId: string, payload: unknown) => {
      assert.equal(collectionId, "col-1");
      assert.equal(releaseId, "rel-1");
      assert.deepEqual(payload, {
        channel: "active",
        trafficPercent: 100,
        notes: "ship it",
      });
    },
  });
  mockModule("@/entities/release/api/rollback-release", {
    rollbackRelease: async (collectionId: string, releaseId: string, payload: unknown) => {
      assert.equal(collectionId, "col-1");
      assert.equal(releaseId, "rel-1");
      assert.deepEqual(payload, {
        rollbackToReleaseId: "rel-0",
        channel: "canary",
        notes: "rollback",
      });
    },
  });

  const module = importFresh<typeof import("./release-actions")>(
    "@/features/release-management/actions/release-actions",
  );

  const createData = new FormData();
  createData.set("taxonomyVersionId", "tax-1");
  createData.set("releaseName", "Spring");
  createData.set("channel", "canary");
  createData.set("trafficPercent", "15");
  createData.set("notes", "qa");
  const createResult = await module.createReleaseAction("col-1", { status: "idle" }, createData);

  const promoteData = new FormData();
  promoteData.set("channel", "active");
  promoteData.set("trafficPercent", "100");
  promoteData.set("notes", "ship it");
  await module.promoteReleaseAction("col-1", "rel-1", promoteData);

  const rollbackData = new FormData();
  rollbackData.set("rollbackToReleaseId", "rel-0");
  rollbackData.set("channel", "canary");
  rollbackData.set("notes", "rollback");
  await module.rollbackReleaseAction("col-1", "rel-1", rollbackData);

  assert.deepEqual(createResult, { status: "success", message: "Release created." });
  assert.deepEqual(nextCache.__getCalls(), ["/collections/col-1", "/collections/col-1", "/collections/col-1"]);

  restoreModules([
    "@/features/release-management/actions/release-actions",
    "@/entities/release/api/create-release",
    "@/entities/release/api/promote-release",
    "@/entities/release/api/rollback-release",
  ]);
});

test("createReleaseAction returns error state on failure", async () => {
  mockModule("@/entities/release/api/create-release", {
    createRelease: async () => {
      throw new Error("release failed");
    },
  });
  mockModule("@/entities/release/api/promote-release", {
    promoteRelease: async () => undefined,
  });
  mockModule("@/entities/release/api/rollback-release", {
    rollbackRelease: async () => undefined,
  });

  const { createReleaseAction } = importFresh<typeof import("./release-actions")>(
    "@/features/release-management/actions/release-actions",
  );
  const formData = new FormData();
  const result = await createReleaseAction("col-1", { status: "idle" }, formData);

  assert.deepEqual(result, {
    status: "error",
    message: "release failed",
  });

  restoreModules([
    "@/features/release-management/actions/release-actions",
    "@/entities/release/api/create-release",
    "@/entities/release/api/promote-release",
    "@/entities/release/api/rollback-release",
  ]);
});
