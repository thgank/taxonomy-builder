package com.taxonomy.api.messaging;

import java.util.Map;
import java.util.UUID;

public record PipelineMessage(
        UUID jobId,
        UUID collectionId,
        UUID taxonomyVersionId,
        String jobType,
        Map<String, Object> params,
        String correlationId,
        String traceId
) {
    public static PipelineMessage of(UUID jobId, UUID collectionId,
                                     UUID taxonomyVersionId,
                                     String jobType,
                                     Map<String, Object> params,
                                     String correlationId,
                                     String traceId) {
        return new PipelineMessage(jobId, collectionId, taxonomyVersionId,
                jobType, params, correlationId, traceId);
    }
}
