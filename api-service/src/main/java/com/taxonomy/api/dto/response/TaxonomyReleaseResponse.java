package com.taxonomy.api.dto.response;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record TaxonomyReleaseResponse(
        UUID id,
        UUID collectionId,
        UUID taxonomyVersionId,
        String releaseName,
        String channel,
        Integer trafficPercent,
        Boolean isActive,
        UUID rollbackOf,
        Map<String, Object> qualitySnapshot,
        String notes,
        Instant createdAt
) {}
