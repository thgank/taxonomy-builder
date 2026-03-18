import type {
  Job,
  JobEvent,
  JobPipelineSnapshot,
  JobType,
  PipelineStage,
  PipelineStageKey,
  PipelineStageState,
} from "@/entities/job/types/job";

const stageDefinitions: Record<JobType, PipelineStage[]> = {
  FULL_PIPELINE: [
    { key: "import", label: "Import" },
    { key: "nlp", label: "NLP" },
    { key: "terms", label: "Terms" },
    { key: "build", label: "Build" },
    { key: "evaluate", label: "Evaluate" },
  ],
  IMPORT: [{ key: "import", label: "Import" }],
  NLP: [{ key: "nlp", label: "NLP" }],
  TERMS: [{ key: "terms", label: "Terms" }],
  TAXONOMY: [{ key: "build", label: "Build" }],
  EVALUATE: [{ key: "evaluate", label: "Evaluate" }],
};

const eventStageMatchers: Array<{ key: PipelineStageKey; test: RegExp[] }> = [
  {
    key: "import",
    test: [
      /^import started/i,
      /^parsed /i,
      /no new documents/i,
      /during import/i,
      /unsupported mime/i,
      /empty text extracted/i,
      /failed to parse/i,
    ],
  },
  {
    key: "nlp",
    test: [/nlp preprocessing started/i, /^nlp finished/i, /no chunks to process/i],
  },
  {
    key: "terms",
    test: [
      /term extraction started/i,
      /tf-idf extracted/i,
      /textrank extracted/i,
      /after dedup/i,
      /term extraction complete/i,
      /chunk language split/i,
      /no chunks found for term extraction/i,
    ],
  },
  {
    key: "build",
    test: [
      /taxonomy build started/i,
      /hearst patterns/i,
      /embedding clustering/i,
      /adaptive edge accept/i,
      /candidate edge logs persisted/i,
      /after post-processing/i,
      /quality gate/i,
      /orphan safe-linking/i,
      /component bridging/i,
      /anchor bridging/i,
      /global selector/i,
      /taxonomy build complete/i,
      /no taxonomy relations found/i,
      /no concepts found/i,
    ],
  },
  {
    key: "evaluate",
    test: [
      /evaluation started/i,
      /structural metrics/i,
      /edge confidence/i,
      /fragmentation\/risk/i,
      /evaluation complete/i,
      /quality_score/i,
    ],
  },
];

export function getPipelineStages(jobType: JobType) {
  return stageDefinitions[jobType];
}

function inferStageKey(event: JobEvent): PipelineStageKey | null {
  const message = event.message;

  for (const matcher of eventStageMatchers) {
    if (matcher.test.some((pattern) => pattern.test(message))) {
      return matcher.key;
    }
  }

  const terminalStageMatch = message.match(/terminal stage:\s*(import|nlp|terms|build|evaluate)/i);
  if (terminalStageMatch) {
    return terminalStageMatch[1].toLowerCase() as PipelineStageKey;
  }

  return null;
}

function currentStageIndex(job: Job, events: JobEvent[]) {
  const stages = getPipelineStages(job.type);
  const indexes = events
    .map(inferStageKey)
    .map((stage) => stages.findIndex((item) => item.key === stage))
    .filter((index) => index >= 0);

  if (indexes.length > 0) {
    return Math.max(...indexes);
  }

  return 0;
}

function stageStateForIndex(
  stageIndex: number,
  currentIndex: number,
  jobStatus: Job["status"],
): PipelineStageState {
  if (jobStatus === "SUCCESS") {
    return "completed";
  }

  if (stageIndex < currentIndex) {
    return "completed";
  }

  if (stageIndex > currentIndex) {
    return "pending";
  }

  switch (jobStatus) {
    case "QUEUED":
      return "queued";
    case "RUNNING":
      return "running";
    case "RETRYING":
      return "retrying";
    case "FAILED":
      return "failed";
    case "CANCELLED":
      return "cancelled";
    default:
      return "pending";
  }
}

export function deriveJobPipelineSnapshot(job: Job, events: JobEvent[]): JobPipelineSnapshot {
  const stages = getPipelineStages(job.type);
  const currentIndex = currentStageIndex(job, events);

  const stageItems = stages.map((stage, stageIndex) => {
    const stageEvents = events.filter((event) => inferStageKey(event) === stage.key);
    const latestEvent = stageEvents.at(-1);
    const state = stageStateForIndex(stageIndex, currentIndex, job.status);

    return {
      ...stage,
      state,
      progress:
        state === "completed"
          ? 100
          : stageIndex === currentIndex && ["running", "retrying", "failed", "cancelled"].includes(state)
            ? job.progress
            : 0,
      latestMessage: latestEvent?.message ?? null,
      latestTimestamp: latestEvent?.ts ?? null,
      events: stageEvents,
    };
  });

  const totalStages = Math.max(stageItems.length, 1);
  const overallProgress =
    job.status === "SUCCESS"
      ? 100
      : Math.round(
          ((Math.max(currentIndex, 0) + (job.status === "QUEUED" ? 0 : job.progress / 100)) /
            totalStages) *
            100,
        );

  return {
    job,
    events,
    stages: stageItems,
    overallProgress,
    currentStageKey: stageItems[currentIndex]?.key ?? null,
  };
}
