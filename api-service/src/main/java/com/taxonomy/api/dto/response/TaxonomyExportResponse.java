package com.taxonomy.api.dto.response;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record TaxonomyExportResponse(
        UUID taxonomyVersionId,
        UUID collectionId,
        String algorithm,
        Map<String, Object> parameters,
        Map<String, Object> qualityMetrics,
        List<ExportNode> nodes,
        List<ExportEdge> edges
) {
    public record ExportNode(UUID id, String label) {}

    public record ExportEdge(
            UUID parent,
            UUID child,
            Double score,
            List<Map<String, Object>> evidence
    ) {}
}
