package com.taxonomy.api.dto.response;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record TaxonomyEdgeResponse(
        UUID id,
        UUID parentConceptId,
        String parentLabel,
        UUID childConceptId,
        String childLabel,
        String relation,
        Double score,
        List<Map<String, Object>> evidence
) {}
