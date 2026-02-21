package com.taxonomy.api.messaging;

import java.util.Map;
import java.util.UUID;

public record PipelineMessage(
        UUID jobId,
        UUID collectionId,
        UUID taxonomyVersionId,
        Map<String, Object> params,
        String correlationId,
        String traceId
) {
    public static PipelineMessage of(UUID jobId, UUID collectionId,
                                     UUID taxonomyVersionId,
                                     Map<String, Object> params) {
        String traceId = UUID.randomUUID().toString();
        return new PipelineMessage(jobId, collectionId, taxonomyVersionId,
                params, traceId, traceId);
    }
}
