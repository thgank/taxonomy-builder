import assert from "node:assert/strict";
import test from "node:test";

import { importFresh, mockModule, restoreModules } from "../../../../test/module-test-utils";

const targetModule = "@/entities/job/model/get-job-pipeline-snapshot";
const modulesToReset = [
  targetModule,
  "@/entities/job/api/get-job",
  "@/entities/job/api/get-job-events",
  "@/shared/lib/pipeline",
];

test("getJobPipelineSnapshot loads job and events and derives snapshot", async () => {
  mockModule("@/entities/job/api/get-job", {
    getJob: async (jobId: string) => ({ id: jobId, type: "FULL_PIPELINE" }),
  });
  mockModule("@/entities/job/api/get-job-events", {
    getJobEvents: async (jobId: string) => [{ id: `${jobId}-evt` }],
  });
  mockModule("@/shared/lib/pipeline", {
    deriveJobPipelineSnapshot: (job: unknown, events: unknown) => ({ job, events, derived: true }),
  });

  const { getJobPipelineSnapshot } = importFresh<typeof import("./get-job-pipeline-snapshot")>(targetModule);
  const snapshot = await getJobPipelineSnapshot("job-42");

  assert.deepEqual(snapshot, {
    job: { id: "job-42", type: "FULL_PIPELINE" },
    events: [{ id: "job-42-evt" }],
    derived: true,
  });

  restoreModules(modulesToReset);
});

