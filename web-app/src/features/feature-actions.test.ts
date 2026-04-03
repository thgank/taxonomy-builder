import assert from "node:assert/strict";
import test from "node:test";

import { ApiError } from "@/shared/api/error";
import { importFresh, mockModule, restoreModules } from "../../test/module-test-utils";

const nextCache = require("next/cache") as {
  __getCalls(): string[];
  __reset(): void;
};

test("createCollectionAction validates input, succeeds, and handles API errors", async () => {
  nextCache.__reset();
  const target = "@/features/create-collection/actions/create-collection-action";
  mockModule("@/entities/collection/api/create-collection", {
    createCollection: async () => ({ id: "unused" }),
  });

  let module = importFresh<typeof import("./create-collection/actions/create-collection-action")>(target);
  const invalid = await module.createCollectionAction({ name: "   ", description: "desc" });
  assert.equal(invalid.success, false);
  assert.equal(invalid.message, "Please correct the highlighted fields.");

  mockModule("@/entities/collection/api/create-collection", {
    createCollection: async () => ({ id: "col-1" }),
  });
  module = importFresh<typeof import("./create-collection/actions/create-collection-action")>(target);
  const success = await module.createCollectionAction({ name: "Energy", description: "" });
  assert.deepEqual(success, { success: true, collectionId: "col-1" });
  assert.deepEqual(nextCache.__getCalls(), ["/collections"]);

  nextCache.__reset();
  mockModule("@/entities/collection/api/create-collection", {
    createCollection: async () => {
      throw new ApiError("Collection exists", 409);
    },
  });
  module = importFresh<typeof import("./create-collection/actions/create-collection-action")>(target);
  const apiError = await module.createCollectionAction({ name: "Energy", description: "" });
  assert.equal(apiError.success, false);
  assert.equal(apiError.message, "Collection exists");

  restoreModules([
    target,
    "@/entities/collection/api/create-collection",
  ]);
});

test("createJobAction validates input, parses params, and returns failures", async () => {
  nextCache.__reset();
  const target = "@/features/create-job/actions/create-job-action";
  mockModule("@/entities/job/api/create-job", {
    createJob: async () => ({ id: "unused" }),
  });

  let module = importFresh<typeof import("./create-job/actions/create-job-action")>(target);
  const invalid = await module.createJobAction("col-1", {
    type: "IMPORT",
    paramsText: "{bad",
  });
  assert.equal(invalid.success, false);
  assert.equal(invalid.message, "Please correct the job configuration before submitting.");

  mockModule("@/entities/job/api/create-job", {
    createJob: async (collectionId: string, payload: unknown) => {
      assert.equal(collectionId, "col-1");
      assert.deepEqual(payload, {
        type: "FULL_PIPELINE",
        params: { chunk_size: 100 },
      });
      return { id: "job-1" };
    },
  });
  module = importFresh<typeof import("./create-job/actions/create-job-action")>(target);
  const success = await module.createJobAction("col-1", {
    type: "FULL_PIPELINE",
    paramsText: '{"chunk_size":100}',
  });
  assert.deepEqual(success, { success: true, jobId: "job-1" });
  assert.deepEqual(nextCache.__getCalls(), ["/collections/col-1"]);

  nextCache.__reset();
  mockModule("@/entities/job/api/create-job", {
    createJob: async () => {
      throw new Error("boom");
    },
  });
  module = importFresh<typeof import("./create-job/actions/create-job-action")>(target);
  const genericError = await module.createJobAction("col-1", {
    type: "IMPORT",
    paramsText: "",
  });
  assert.equal(genericError.success, false);
  assert.equal(genericError.message, "Failed to create processing job.");

  restoreModules([
    target,
    "@/entities/job/api/create-job",
  ]);
});

test("cancelJobAction revalidates both job and collection pages", async () => {
  nextCache.__reset();
  mockModule("@/entities/job/api/cancel-job", {
    cancelJob: async (jobId: string) => assert.equal(jobId, "job-1"),
  });

  const { cancelJobAction } = importFresh<typeof import("./pipeline-monitor/actions/cancel-job-action")>(
    "@/features/pipeline-monitor/actions/cancel-job-action",
  );

  await cancelJobAction("job-1", "col-1");

  assert.deepEqual(nextCache.__getCalls(), ["/jobs/job-1", "/collections/col-1"]);

  restoreModules([
    "@/features/pipeline-monitor/actions/cancel-job-action",
    "@/entities/job/api/cancel-job",
  ]);
});

test("uploadDocumentsAction validates files, succeeds, and reports upload errors", async () => {
  nextCache.__reset();
  const target = "@/features/upload-documents/actions/upload-documents-action";
  mockModule("@/entities/document/api/upload-documents", {
    uploadCollectionDocuments: async () => [],
  });

  let module = importFresh<typeof import("./upload-documents/actions/upload-documents-action")>(target);
  const emptyResult = await module.uploadDocumentsAction("col-1", { status: "idle" }, new FormData());
  assert.deepEqual(emptyResult, {
    status: "error",
    message: "Select at least one file before uploading.",
  });

  mockModule("@/entities/document/api/upload-documents", {
    uploadCollectionDocuments: async (_collectionId: string, files: File[]) => {
      assert.equal(files.length, 2);
      return [{ id: "doc-1" }, { id: "doc-2" }];
    },
  });
  module = importFresh<typeof import("./upload-documents/actions/upload-documents-action")>(target);
  const formData = new FormData();
  formData.append("files", new File(["a"], "a.txt"));
  formData.append("files", new File(["b"], "b.txt"));
  const success = await module.uploadDocumentsAction("col-1", { status: "idle" }, formData);
  assert.deepEqual(success, {
    status: "success",
    message: "Uploaded 2 documents.",
  });
  assert.deepEqual(nextCache.__getCalls(), ["/collections/col-1"]);

  nextCache.__reset();
  mockModule("@/entities/document/api/upload-documents", {
    uploadCollectionDocuments: async () => {
      throw new Error("upload failed");
    },
  });
  module = importFresh<typeof import("./upload-documents/actions/upload-documents-action")>(target);
  const failingData = new FormData();
  failingData.append("files", new File(["a"], "a.txt"));
  const errorResult = await module.uploadDocumentsAction("col-1", { status: "idle" }, failingData);
  assert.deepEqual(errorResult, {
    status: "error",
    message: "upload failed",
  });

  restoreModules([
    target,
    "@/entities/document/api/upload-documents",
  ]);
});
