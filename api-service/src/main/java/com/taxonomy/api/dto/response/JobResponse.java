package com.taxonomy.api.dto.response;

import java.time.Instant;
import java.util.UUID;

public record JobResponse(
        UUID id,
        UUID collectionId,
        UUID taxonomyVersionId,
        String type,
        String status,
        int progress,
        String errorMessage,
        Instant createdAt,
        Instant startedAt,
        Instant finishedAt
) {}
