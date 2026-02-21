package com.taxonomy.api.dto.response;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record TaxonomyVersionResponse(
        UUID id,
        UUID collectionId,
        String algorithm,
        Map<String, Object> parameters,
        Map<String, Object> qualityMetrics,
        String status,
        Instant createdAt,
        Instant finishedAt,
        long edgeCount,
        long conceptCount
) {}
