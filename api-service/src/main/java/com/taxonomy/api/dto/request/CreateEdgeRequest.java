package com.taxonomy.api.dto.request;

import jakarta.validation.constraints.NotNull;

import java.util.UUID;

public record CreateEdgeRequest(
        @NotNull UUID parentConceptId,
        @NotNull UUID childConceptId,
        String relation,
        Double score
) {}
