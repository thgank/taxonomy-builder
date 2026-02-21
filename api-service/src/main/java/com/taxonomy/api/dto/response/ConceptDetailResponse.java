package com.taxonomy.api.dto.response;

import java.util.List;
import java.util.UUID;

public record ConceptDetailResponse(
        UUID id,
        String canonical,
        List<String> surfaceForms,
        String lang,
        Double score,
        List<RelatedConcept> parents,
        List<RelatedConcept> children,
        List<OccurrenceInfo> occurrences
) {
    public record RelatedConcept(UUID id, String canonical, Double edgeScore) {}

    public record OccurrenceInfo(
            UUID chunkId,
            UUID documentId,
            String snippet,
            Double confidence
    ) {}
}
