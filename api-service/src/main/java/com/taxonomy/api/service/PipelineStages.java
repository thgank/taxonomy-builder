package com.taxonomy.api.service;

import com.taxonomy.api.entity.enums.JobType;

import java.util.List;
import java.util.Map;

/**
 * Declarative pipeline stage definitions per job type.
 * Each job type declares its ordered sequence of stages (RabbitMQ routing keys).
 */
public final class PipelineStages {

    private PipelineStages() {}

    /**
     * Ordered list of routing keys for each job type.
     * The first entry is published immediately on job creation;
     * after each stage completes, the worker publishes the next one.
     */
    private static final Map<JobType, List<String>> STAGE_MAP = Map.of(
            JobType.FULL_PIPELINE, List.of("import", "nlp", "terms", "build", "evaluate"),
            JobType.IMPORT,        List.of("import"),
            JobType.NLP,           List.of("nlp"),
            JobType.TERMS,         List.of("terms"),
            JobType.TAXONOMY,      List.of("build"),
            JobType.EVALUATE,      List.of("evaluate")
    );

    /**
     * Get the ordered list of stages for a job type.
     */
    public static List<String> stagesFor(JobType type) {
        return STAGE_MAP.getOrDefault(type, List.of());
    }

    /**
     * Get the first (entry) routing key for a job type.
     */
    public static String firstStage(JobType type) {
        List<String> stages = stagesFor(type);
        if (stages.isEmpty()) {
            throw new IllegalArgumentException("No stages defined for job type: " + type);
        }
        return stages.getFirst();
    }

    /**
     * Get the next routing key after the current stage, or null if terminal.
     */
    public static String nextStage(JobType type, String currentStage) {
        List<String> stages = stagesFor(type);
        int idx = stages.indexOf(currentStage);
        if (idx < 0 || idx + 1 >= stages.size()) {
            return null; // terminal
        }
        return stages.get(idx + 1);
    }

    /**
     * Check if a stage is the terminal (last) stage for a job type.
     */
    public static boolean isTerminal(JobType type, String stage) {
        List<String> stages = stagesFor(type);
        return !stages.isEmpty() && stages.getLast().equals(stage);
    }
}
