export const jobTypes = [
  "IMPORT",
  "NLP",
  "TERMS",
  "TAXONOMY",
  "FULL_PIPELINE",
  "EVALUATE",
] as const;

export type JobType = (typeof jobTypes)[number];

export interface Job {
  id: string;
  collectionId: string;
  taxonomyVersionId: string | null;
  type: JobType;
  status: "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED" | "CANCELLED" | "RETRYING";
  progress: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface JobEvent {
  id: string;
  ts: string;
  level: string;
  message: string;
  meta: Record<string, unknown> | null;
}

export interface CreateJobRequest {
  type: JobType;
  params: Record<string, unknown>;
}

export type PipelineStageKey = "import" | "nlp" | "terms" | "build" | "evaluate";
export type PipelineStageState =
  | "pending"
  | "queued"
  | "running"
  | "retrying"
  | "completed"
  | "failed"
  | "cancelled";

export interface PipelineStage {
  key: PipelineStageKey;
  label: string;
}

export interface PipelineStageSnapshot extends PipelineStage {
  state: PipelineStageState;
  progress: number;
  latestMessage: string | null;
  latestTimestamp: string | null;
  events: JobEvent[];
}

export interface JobPipelineSnapshot {
  job: Job;
  events: JobEvent[];
  stages: PipelineStageSnapshot[];
  overallProgress: number;
  currentStageKey: PipelineStageKey | null;
}
