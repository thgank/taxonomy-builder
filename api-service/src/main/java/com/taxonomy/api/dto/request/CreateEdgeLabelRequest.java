package com.taxonomy.api.dto.request;

import java.util.Map;
import java.util.UUID;

public record CreateEdgeLabelRequest(
        UUID candidateId,
        UUID parentConceptId,
        UUID childConceptId,
        String parentLabel,
        String childLabel,
        String label,
        String labelSource,
        String reviewerId,
        String reason,
        Map<String, Object> meta
) {}
