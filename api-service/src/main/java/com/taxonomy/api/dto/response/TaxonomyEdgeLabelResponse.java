package com.taxonomy.api.dto.response;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record TaxonomyEdgeLabelResponse(
        UUID id,
        UUID candidateId,
        UUID taxonomyVersionId,
        UUID collectionId,
        UUID parentConceptId,
        UUID childConceptId,
        String parentLabel,
        String childLabel,
        String label,
        String labelSource,
        String reviewerId,
        String reason,
        Map<String, Object> meta,
        Instant createdAt
) {}
