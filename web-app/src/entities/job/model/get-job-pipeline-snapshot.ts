import { getJob } from "@/entities/job/api/get-job";
import { getJobEvents } from "@/entities/job/api/get-job-events";
import type { JobPipelineSnapshot } from "@/entities/job/types/job";
import { deriveJobPipelineSnapshot } from "@/shared/lib/pipeline";

export async function getJobPipelineSnapshot(jobId: string): Promise<JobPipelineSnapshot> {
  const [job, events] = await Promise.all([getJob(jobId), getJobEvents(jobId)]);

  return deriveJobPipelineSnapshot(job, events);
}
