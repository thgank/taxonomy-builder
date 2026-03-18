import { notFound } from "next/navigation";

import { getJobPipelineSnapshot } from "@/entities/job/model/get-job-pipeline-snapshot";
import { isApiError } from "@/shared/api/error";
import { JobDetails } from "@/widgets/job-details/job-details";

export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  let snapshotData: Awaited<ReturnType<typeof getJobPipelineSnapshot>>;

  try {
    snapshotData = await getJobPipelineSnapshot(jobId);
  } catch (error) {
    if (isApiError(error) && error.status === 404) {
      notFound();
    }

    throw error;
  }

  return <JobDetails snapshot={snapshotData} />;
}
