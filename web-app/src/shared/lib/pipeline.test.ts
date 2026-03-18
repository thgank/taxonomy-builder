import assert from "node:assert/strict";
import test from "node:test";

import { deriveJobPipelineSnapshot, getPipelineStages } from "./pipeline";

test("getPipelineStages returns the expected stage order", () => {
  assert.deepEqual(getPipelineStages("FULL_PIPELINE"), [
    { key: "import", label: "Import" },
    { key: "nlp", label: "NLP" },
    { key: "terms", label: "Terms" },
    { key: "build", label: "Build" },
    { key: "evaluate", label: "Evaluate" },
  ]);
});

test("deriveJobPipelineSnapshot marks completed and current stages from events", () => {
  const job = {
    id: "job-1",
    collectionId: "collection-1",
    taxonomyVersionId: "taxonomy-1",
    type: "FULL_PIPELINE" as const,
    status: "RUNNING" as const,
    progress: 80,
    errorMessage: null,
    createdAt: "2026-03-18T10:00:00Z",
    startedAt: "2026-03-18T10:00:10Z",
    finishedAt: null,
  };
  const events = [
    {
      id: "evt-1",
      ts: "2026-03-18T10:00:10Z",
      level: "INFO",
      message: "Import started",
      meta: null,
    },
    {
      id: "evt-2",
      ts: "2026-03-18T10:01:10Z",
      level: "INFO",
      message: "NLP preprocessing started",
      meta: null,
    },
    {
      id: "evt-3",
      ts: "2026-03-18T10:02:10Z",
      level: "INFO",
      message: "Term extraction started",
      meta: null,
    },
    {
      id: "evt-4",
      ts: "2026-03-18T10:03:10Z",
      level: "INFO",
      message: "Taxonomy build started",
      meta: null,
    },
  ];

  const snapshot = deriveJobPipelineSnapshot(job, events);

  assert.equal(snapshot.currentStageKey, "build");
  assert.equal(snapshot.stages[0]?.state, "completed");
  assert.equal(snapshot.stages[1]?.state, "completed");
  assert.equal(snapshot.stages[2]?.state, "completed");
  assert.equal(snapshot.stages[3]?.state, "running");
  assert.equal(snapshot.stages[3]?.progress, 80);
  assert.equal(snapshot.stages[3]?.latestMessage, "Taxonomy build started");
  assert.equal(snapshot.stages[4]?.state, "pending");
  assert.equal(snapshot.overallProgress, 76);
});

test("deriveJobPipelineSnapshot marks all stages completed for successful jobs", () => {
  const job = {
    id: "job-2",
    collectionId: "collection-1",
    taxonomyVersionId: "taxonomy-1",
    type: "IMPORT" as const,
    status: "SUCCESS" as const,
    progress: 100,
    errorMessage: null,
    createdAt: "2026-03-18T10:00:00Z",
    startedAt: "2026-03-18T10:00:10Z",
    finishedAt: "2026-03-18T10:00:20Z",
  };

  const snapshot = deriveJobPipelineSnapshot(job, []);

  assert.equal(snapshot.currentStageKey, "import");
  assert.equal(snapshot.stages[0]?.state, "completed");
  assert.equal(snapshot.stages[0]?.progress, 100);
  assert.equal(snapshot.overallProgress, 100);
});
