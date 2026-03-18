import { NextResponse } from "next/server";

import { getJobPipelineSnapshot } from "@/entities/job/model/get-job-pipeline-snapshot";
import { isApiError } from "@/shared/api/error";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;

  try {
    const snapshot = await getJobPipelineSnapshot(jobId);
    return NextResponse.json(snapshot);
  } catch (error) {
    if (isApiError(error)) {
      return NextResponse.json(
        { message: error.message, status: error.status },
        { status: error.status },
      );
    }

    return NextResponse.json({ message: "Failed to load pipeline snapshot." }, { status: 500 });
  }
}
